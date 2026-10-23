"""End-to-end answer-page pipeline: page image -> deskew -> rule removal -> binarise (optional)
-> line segmentation -> CRNN-CTC recognition -> per-line confidence and review flag.

The recogniser never sees expected answers or rubrics. Low-confidence lines are flagged
as "cannot read confidently" rather than being guessed.
"""
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

import crnn
import htr_data as H


@dataclass
class Config:
    deskew: bool = True
    binarise: str = "none"          # none | otsu | clahe
    remove_rules: bool = True
    profile_thr: float = 0.02       # fraction of max row-ink needed to start a line band (validation-chosen)
    ink_thr: int = 0                # 0 = Otsu; otherwise pixels darker than this count as ink
    pad: int = 14                   # vertical padding (px) added around each detected band (validation-chosen)
    min_band_h: int = 14
    conf_flag: float = 0.95         # lines below this mean confidence are flagged for review (validation-chosen)


@dataclass
class Segment:
    y0: int
    y1: int
    text: str = ""
    conf: float = 0.0
    flagged: bool = False


@dataclass
class PageResult:
    segments: list = field(default_factory=list)
    timings: dict = field(default_factory=dict)


def estimate_skew(ink):
    """Projection-profile skew search: coarse pass over -3..3 deg, then a fine pass around the best angle."""
    small = cv2.resize(ink, (ink.shape[1] // 2, ink.shape[0] // 2), interpolation=cv2.INTER_AREA)
    h, w = small.shape

    def score(a):
        M = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1.0)
        r = cv2.warpAffine(small, M, (w, h))
        return r.sum(axis=1).astype(np.float64).var()

    coarse = max(np.arange(-3.0, 3.01, 0.25), key=score)
    fine = max(np.arange(coarse - 0.25, coarse + 0.26, 0.05), key=score)
    return float(fine)


def preprocess(gray, cfg):
    t = {}
    t0 = time.perf_counter()
    g = gray.copy()
    if cfg.deskew:
        _, ink0 = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        a = estimate_skew(ink0)
        M = cv2.getRotationMatrix2D((g.shape[1] / 2, g.shape[0] / 2), a, 1.0)
        g = cv2.warpAffine(g, M, (g.shape[1], g.shape[0]), borderValue=255)
        t["deskew_deg"] = a
    if cfg.remove_rules:
        # long horizontal ruled lines and the vertical margin rule are whitened so they cannot
        # widen line crops; strokes darker than 150 are kept even where they touch a rule
        dark = (g < 225).astype(np.uint8) * 255
        for kernel in ((120, 1), (1, 120)):
            rules = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, kernel))
            g[(rules > 0) & (g > 150)] = 255
    if cfg.binarise == "otsu":
        _, g = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif cfg.binarise == "clahe":
        g = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(g)
    t["preprocess_s"] = time.perf_counter() - t0
    return g, t


def segment(gray, cfg):
    if cfg.ink_thr > 0:
        ink = np.where(gray < cfg.ink_thr, 255, 0).astype(np.uint8)
    else:
        _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    prof = (ink > 0).sum(axis=1).astype(np.float64)
    prof = np.convolve(prof, np.ones(5) / 5, mode="same")
    thr = cfg.profile_thr * prof.max()
    on = prof > thr
    bands, start = [], None
    for y, v in enumerate(on):
        if v and start is None:
            start = y
        if not v and start is not None:
            bands.append([start, y]); start = None
    if start is not None:
        bands.append([start, len(on)])
    # merge close bands, drop tiny ones
    merged = []
    for b in bands:
        if merged and b[0] - merged[-1][1] < 6:
            merged[-1][1] = b[1]
        else:
            merged.append(b)
    out = []
    pad = cfg.pad
    for y0, y1 in merged:
        if y1 - y0 < cfg.min_band_h:
            continue
        y0p, y1p = max(0, y0 - pad), min(gray.shape[0], y1 + pad)
        cols = np.where(ink[y0p:y1p].sum(axis=0) > 0)[0]
        if cols.size == 0:
            continue
        x0, x1 = max(0, cols[0] - 6), min(gray.shape[1], cols[-1] + 6)
        out.append((y0p, y1p, x0, x1))
    return out


def recognise(gray, cfg, model, charset):
    t = {}
    t0 = time.perf_counter()
    g, t_pre = preprocess(gray, cfg)
    t.update(t_pre)
    t1 = time.perf_counter()
    crops = segment(g, cfg)
    t["segment_s"] = time.perf_counter() - t1
    res = PageResult(timings=t)
    if not crops:
        return res
    t2 = time.perf_counter()
    batch = np.stack([H.to_network(g[y0:y1, x0:x1]) for (y0, y1, x0, x1) in crops])
    import torch
    with torch.no_grad():
        logits = model(torch.from_numpy(batch.astype(np.float32) / 127.5 - 1.0)[:, None]).numpy()
    for (y0, y1, _, _), lg in zip(crops, logits):
        text, conf = crnn.greedy_decode(lg, charset)
        res.segments.append(Segment(y0=y0, y1=y1, text=text, conf=conf, flagged=conf < cfg.conf_flag))
    t["recognise_s"] = time.perf_counter() - t2
    t["total_s"] = time.perf_counter() - t0
    return res


def match_to_gt(segments, gt_lines):
    """Match each GT line to the segment with the largest vertical overlap (IoU > 0.3)."""
    pairs = []
    used = set()
    for gi, (text, gy0, gy1) in enumerate(gt_lines):
        best, best_iou = None, 0.3
        for si, s in enumerate(segments):
            if si in used:
                continue
            inter = max(0, min(gy1, s.y1) - max(gy0, s.y0))
            union = max(gy1, s.y1) - min(gy0, s.y0)
            iou = inter / union if union > 0 else 0
            if iou > best_iou:
                best, best_iou = si, iou
        if best is not None:
            used.add(best)
            pairs.append((gi, best))
        else:
            pairs.append((gi, None))
    spurious = [si for si in range(len(segments)) if si not in used]
    return pairs, spurious


def score_page(res, gt_lines, conf_flag):
    """Score one page. A line is flagged when its confidence is below conf_flag or it is missing."""
    pairs, spurious = match_to_gt(res.segments, gt_lines)
    char_err = char_tot = word_err = word_tot = 0
    flagged_err = flagged_n = clean_err = clean_n = 0
    matched = 0
    for gi, si in pairs:
        ref = gt_lines[gi][0]
        if si is None:
            pred, flag = "", True
        else:
            matched += 1
            pred = res.segments[si].text
            flag = res.segments[si].conf < conf_flag
        e = crnn.edit_distance(pred, ref)
        char_err += e; char_tot += len(ref)
        rw, pw = ref.split(), pred.split()
        word_err += _word_ed(pw, rw)
        word_tot += len(rw)
        if flag:
            flagged_err += int(e > 0); flagged_n += 1
        else:
            clean_err += int(e > 0); clean_n += 1
    return {
        "cer": char_err / max(1, char_tot),
        "wer": word_err / max(1, word_tot),
        "gt_lines": len(gt_lines),
        "matched_lines": matched,
        "line_recall": matched / max(1, len(gt_lines)),
        "spurious_segments": len(spurious),
        "flagged_lines": flagged_n,
        "flagged_line_error_rate": flagged_err / max(1, flagged_n),
        "unflagged_line_error_rate": clean_err / max(1, clean_n),
        "pages_time_s": res.timings.get("total_s", 0.0),
    }


def _word_ed(a, b):
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]
