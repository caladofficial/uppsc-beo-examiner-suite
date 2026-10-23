"""End-to-end answer-page pipeline (packaged copy of ml/htr/pipeline.py; keep in sync): page image -> deskew -> rule removal -> binarise (optional)
-> line segmentation -> CRNN-CTC recognition -> per-line confidence and review flag.

The recogniser never sees expected answers or rubrics. Low-confidence lines are flagged
as "cannot read confidently" rather than being guessed.
"""
import os
import re
import sys
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # allow `import htr_crnn` when loaded by path
import htr_crnn as crnn  # noqa: E402

LINE_H, LINE_W = 40, 320  # network input size, must match the trained checkpoint


def to_network(arr):
    """Normalise a line image to height LINE_H, width LINE_W (compress or pad). Same as htr_data.to_network."""
    h, w = arr.shape
    scale = LINE_H / h
    nw = max(8, int(round(w * scale)))
    arr = cv2.resize(arr, (nw, LINE_H), interpolation=cv2.INTER_AREA)
    if nw > LINE_W:
        arr = cv2.resize(arr, (LINE_W, LINE_H), interpolation=cv2.INTER_AREA)
    else:
        pad = np.full((LINE_H, LINE_W), 255, np.uint8)
        pad[:, :nw] = arr
        arr = pad
    return arr


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


def _split_wide(crop, ink_thr_mask=None):
    """Split a line crop that is wider than the model's training width at word gaps.

    The reader was trained on lines whose height-normalised width is at most LINE_W. Wider lines would
    be squeezed and read as noise, so they are cut at the widest vertical white gap that keeps every
    piece within LINE_W. Returns a list of crops (left to right). Lines that already fit are returned as-is.
    """
    h, w = crop.shape
    scale = LINE_H / h
    max_w = int(LINE_W / scale)
    if w <= max_w:
        return [crop]
    ink = (crop < 128).astype(np.uint8)
    col = ink.sum(axis=0)
    blank = col == 0
    # runs of blank columns
    gaps, start = [], None
    for x in range(w + 1):
        b = x < w and blank[x]
        if b and start is None:
            start = x
        if not b and start is not None:
            gaps.append((start, x))  # [start, end)
            start = None
    min_gap = max(3, int(0.3 * h))
    cuts, x0 = [], 0
    while w - x0 > max_w:
        limit = x0 + max_w
        cands = [(e - s, (s + e) // 2) for (s, e) in gaps if s > x0 + 2 and e <= limit and (e - s) >= 2]
        if not cands:
            cut = limit  # no usable gap: cut hard (rare, very dense strokes)
        else:
            wide = [c for c in cands if c[0] >= min_gap]
            cut = max(wide or cands)[1]
        cuts.append(cut)
        x0 = cut
    bounds = [0] + cuts + [w]
    return [crop[:, a:b] for a, b in zip(bounds[:-1], bounds[1:]) if b - a > 2]


def recognise(gray, cfg, model, charset):
    t = {}
    t0 = time.perf_counter()
    g, t_pre = preprocess(gray, cfg)
    t.update(t_pre)
    t1 = time.perf_counter()
    res = PageResult(timings=t)
    crops = segment(g, cfg)
    t["segment_s"] = time.perf_counter() - t1
    if not crops:
        return res
    t2 = time.perf_counter()
    pieces, owner = [], []
    for idx, (y0, y1, x0, x1) in enumerate(crops):
        for piece in _split_wide(g[y0:y1, x0:x1]):
            pieces.append(to_network(piece))
            owner.append(idx)
    batch = np.stack(pieces)
    import torch
    with torch.no_grad():
        logits = model(torch.from_numpy(batch.astype(np.float32) / 127.5 - 1.0)[:, None]).numpy()
    per_line = {}
    for k, lg in enumerate(logits):
        text, conf = crnn.greedy_decode(lg, charset)
        per_line.setdefault(owner[k], []).append((text, conf))
    for idx, (y0, y1, _, _) in enumerate(crops):
        parts = per_line.get(idx, [])
        text = " ".join(p[0] for p in parts if p[0]).strip()
        conf = float(min(p[1] for p in parts)) if parts else 0.0
        res.segments.append(Segment(y0=y0, y1=y1, text=text, conf=conf, flagged=conf < cfg.conf_flag))
    t["recognise_s"] = time.perf_counter() - t2
    t["total_s"] = time.perf_counter() - t0
    return res


MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "htr_crnn_v3.pt")
ADAPTER_ID = "handwriting_reader_v3"
_MODEL_CACHE = {}


def load_default_model(path=MODEL_PATH):
    if path not in _MODEL_CACHE:
        model, charset = crnn.load_checkpoint(path)
        model.eval()
        _MODEL_CACHE[path] = (model, charset)
    return _MODEL_CACHE[path]


def transcribe_page(image_path, cfg=None):
    """Transcribe one scanned answer page. Returns the same keys the visual OCR reader returns:
    full_transcript, script_detected, overall_confidence, uncertain_spans, adapter_used.
    Lines below the review threshold are returned as uncertain spans; they are never guessed."""
    gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise ValueError("cannot read page image")
    model, charset = load_default_model()
    res = recognise(gray, cfg or Config(), model, charset)
    segs = res.segments  # ordered top to bottom
    confs = [s.conf for s in segs]
    uncertain = [
        {"text": s.text, "alternatives": [], "confidence": round(float(s.conf), 3),
         "reason": "low recognition confidence - needs human check", "line_index": i + 1}
        for i, s in enumerate(segs) if s.flagged
    ]
    has_dev = any(re.search("[\u0900-\u097F]", s.text) for s in segs)
    has_lat = any(re.search("[A-Za-z]", s.text) for s in segs)
    script = "mixed" if (has_dev and has_lat) else ("hi" if has_dev else "en")
    return {
        "full_transcript": "\n".join(s.text for s in segs),
        "script_detected": script,
        "overall_confidence": round(float(np.mean(confs)), 3) if confs else 0.0,
        "uncertain_spans": uncertain,
        "adapter_used": ADAPTER_ID,
        "line_count": len(segs),
        "flagged_line_count": len(uncertain),
    }
