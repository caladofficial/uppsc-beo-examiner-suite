"""Synthetic answer-sheet data for the UPPSC handwritten-answer pipeline.

Source text: real UPPSC BEO Mains question wording and expected answer points, parsed from
apps/web/src/data/import-preview-report.json. Questions are split by id into train / val / test
so that no test sentence is seen during training.

Rendering: Noto Sans / Serif Devanagari (Hindi) and DejaVu Sans (English), shaped with raqm.
Handwriting-like distortion: shear, elastic warp, stroke thickness changes, blur, noise,
lighting gradients, skew and JPEG artefacts. These are SYNTHETIC images with exact labels.
They do not replace real handwritten scans, and accuracy on them is not a field accuracy.
"""
import ast
import hashlib
import json
import random
import re
import unicodedata
import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/home/user")
REPORT = Path(os.environ.get("HTR_REPORT", ROOT / "apps/web/src/data/import-preview-report.json"))
FONTS = {
    "hi": ["/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
           "/usr/share/fonts/truetype/noto/NotoSerifDevanagari-Regular.ttf"],
    "en": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
           "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"],
}
LINE_H = 40          # network input height
LINE_W = 320         # network input width (lines are compressed to fit)


def _lit(x):
    if isinstance(x, (dict, list)):
        return x
    try:
        return ast.literal_eval(x)
    except Exception:
        return x


def load_units():
    """Return list of (question_id, text) units split into short lines of answer-like text."""
    d = json.loads(REPORT.read_text())
    units = []
    for p in d["papers"]:
        for q in p["questions"]:
            qid = q["question_id"]
            cq = _lit(q["canonical_question"])
            if isinstance(cq, dict):
                for lang in ("hi", "en"):
                    if isinstance(cq.get(lang), str):
                        units.append((qid, unicodedata.normalize("NFC", cq[lang])))
            ao = _lit(q["answer_outline"])
            if isinstance(ao, dict):
                for pt in ao.get("expected_points", []) or []:
                    if isinstance(pt, str):
                        units.append((qid, unicodedata.normalize("NFC", pt)))
    return units


def split_of(qid, seed=7):
    h = int(hashlib.sha256(f"{seed}:{qid}".encode()).hexdigest(), 16) % 100
    return "test" if h < 25 else ("val" if h < 40 else "train")


def chunk_units(units, max_chars=34, seed=0):
    """Break units into line-sized chunks at word boundaries (answer-line style)."""
    rng = random.Random(seed)
    out = []
    for qid, text in units:
        words = text.split()
        i = 0
        while i < len(words):
            n = rng.randint(max(3, max_chars // 2), max_chars)
            chunk, length = [], 0
            while i < len(words) and length + len(words[i]) + 1 <= n:
                chunk.append(words[i]); length += len(words[i]) + 1; i += 1
            if not chunk:
                chunk = [words[i][:n]]; i += 1
            out.append((qid, " ".join(chunk)))
    return out


def charset(texts):
    chars = sorted({c for t in texts for c in t})
    return chars


_font_cache = {}


# Fallback when the system Noto Devanagari fonts are not installed (the sandbox was re-provisioned).
# This bundled file is the Noto Sans Devanagari variable font; both Devanagari variants map to it.
HI_FONT_FALLBACK = str(Path(__file__).parent / "fonts" / "NotoSansDevanagari-VF.ttf")
EN_FONT_FALLBACK = str(Path(__file__).parent / "fonts" / "DejaVuSans.ttf")


def font(lang, size, rng):
    key = (lang, size, rng.choice([0, 1]) if lang == "hi" else 0)
    path = FONTS[lang][0 if key[2] == 0 else 1] if lang == "hi" else FONTS["en"][0]
    if lang == "hi" and not os.path.exists(path):
        path = HI_FONT_FALLBACK
    if lang == "en" and not os.path.exists(path):
        path = EN_FONT_FALLBACK
    k = (path, size)
    if k not in _font_cache:
        _font_cache[k] = ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
    return _font_cache[k]


def render_text(text, rng, size=30):
    lang = "hi" if re.search("[\u0900-\u097F]", text) else "en"
    f = font(lang, size, rng)
    bbox = f.getbbox(text)
    w, h = bbox[2] - bbox[0] + 20, bbox[3] - bbox[1] + 20
    img = Image.new("L", (max(w, 10), max(h, 10)), 255)
    ImageDraw.Draw(img).text((10 - bbox[0], 10 - bbox[1]), text, font=f, fill=int(rng.uniform(0, 60)))
    return np.array(img)


def handwrite(arr, rng, strength=1.0):
    """Apply handwriting-like distortion to a white-background grey image (uint8, ink dark)."""
    img = arr.astype(np.float32)
    h, w = img.shape
    # shear / slant
    shear = rng.uniform(-0.25, 0.25) * strength
    ang = rng.uniform(-2.0, 2.0) * strength
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    M[0, 1] += shear
    M[0, 2] -= shear * h / 2
    img = cv2.warpAffine(img, M, (w + int(abs(shear) * h) + 4, h + 4), borderValue=255)
    # elastic warp
    hh, ww = img.shape
    alpha = rng.uniform(0.5, 2.2) * strength
    sigma = rng.uniform(5, 9)
    dx = cv2.GaussianBlur(np.random.default_rng(rng.randint(0, 2**31)).uniform(-1, 1, (hh, ww)).astype(np.float32), (0, 0), sigma) * alpha * 12
    dy = cv2.GaussianBlur(np.random.default_rng(rng.randint(0, 2**31)).uniform(-1, 1, (hh, ww)).astype(np.float32), (0, 0), sigma) * alpha * 12
    gx, gy = np.meshgrid(np.arange(ww, dtype=np.float32), np.arange(hh, dtype=np.float32))
    img = cv2.remap(img, gx + dx, gy + dy, cv2.INTER_LINEAR, borderValue=255)
    # stroke thickness
    ink = 255 - img
    r = rng.random()
    if r < 0.3:
        ink = cv2.dilate(ink, np.ones((2, 2), np.uint8))
    elif r < 0.45:
        ink = cv2.erode(ink, np.ones((2, 2), np.uint8))
    img = 255 - ink
    # blur + noise + lighting
    img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.2, 1.1) * strength)
    img = img + np.random.default_rng(rng.randint(0, 2**31)).normal(0, rng.uniform(2, 12), img.shape).astype(np.float32)
    grad = np.linspace(rng.uniform(0.85, 1.0), rng.uniform(0.85, 1.0), ww)[None, :]
    img = img * grad
    return np.clip(img, 0, 255).astype(np.uint8)


def to_network(arr, rng=None):
    """Normalise a line image to height LINE_H, width LINE_W (compress or pad)."""
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


def synth_line(text, rng, strength=1.0):
    img = render_text(text, rng, size=rng.choice([26, 30, 34]))
    img = handwrite(img, rng, strength)
    return to_network(img)


# ---------------- full page copies (for end-to-end testing) ----------------
PAGE_W, PAGE_H = 1240, 1754  # A4 at about 150 dpi
LINE_SPACING = 58
MARGIN_X, TOP = 120, 260


def wrap(text, max_px, size=34):
    lang = "hi" if re.search("[\u0900-\u097F]", text) else "en"
    f = font(lang, size, random.Random(0))
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        cand = (cur + " " + w_).strip()
        if f.getlength(cand) <= max_px:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def make_copy(texts, seed, strength=1.0):
    """Return (page_gray uint8, [(line_text, y_top, y_bottom)]) for one handwritten-style answer page."""
    rng = random.Random(seed)
    page = np.full((PAGE_H, PAGE_W), 252, np.uint8)
    # ruled lines (light grey) and a header
    for y in range(TOP, PAGE_H - 120, LINE_SPACING):
        page[y, MARGIN_X - 40:PAGE_W - 80] = 200
    page[:, MARGIN_X - 60:MARGIN_X - 58] = 170  # margin rule
    gt = []
    y = TOP - 30
    lines = []
    for t in texts:
        lines.extend(wrap(t, PAGE_W - 2 * MARGIN_X - 60))
    for ln in lines:
        if y + LINE_SPACING > PAGE_H - 120:
            break
        ln_img = handwrite(render_text(ln, rng, size=34), rng, strength)
        lh, lw = ln_img.shape
        x0 = MARGIN_X + rng.randint(0, 12)
        ytop = y + rng.randint(-4, 4)
        ytop = max(0, min(ytop, PAGE_H - lh - 1))
        xe = min(PAGE_W - 1, x0 + lw)
        region = page[ytop:ytop + lh, x0:xe]
        src = ln_img[:region.shape[0], :region.shape[1]]
        mask = src < 200
        region[mask] = np.minimum(region[mask], src[mask])
        gt.append((ln, int(ytop), int(ytop + lh), int(x0), int(xe)))
        y += LINE_SPACING
    # page-level degradation: skew, lighting, noise, JPEG
    ang = rng.uniform(-1.5, 1.5)
    M = cv2.getRotationMatrix2D((PAGE_W / 2, PAGE_H / 2), ang, 1.0)
    page = cv2.warpAffine(page, M, (PAGE_W, PAGE_H), borderValue=255)
    # ground-truth boxes must follow the same rotation: map the four corners and take the bounding box
    gt_rot = []
    for ln, yt, yb, xa, xb in gt:
        pts = np.array([[xa, yt, 1], [xb, yt, 1], [xa, yb, 1], [xb, yb, 1]], np.float64)
        mapped = pts @ M.T
        gt_rot.append((ln, int(round(mapped[:, 1].min())), int(round(mapped[:, 1].max()))))
    gt = gt_rot
    yy, xx = np.mgrid[0:PAGE_H, 0:PAGE_W].astype(np.float32)
    light = 1.0 - rng.uniform(0.05, 0.2) * ((xx / PAGE_W) + (yy / PAGE_H)) / 2
    page = np.clip(page.astype(np.float32) * light + np.random.default_rng(seed).normal(0, 4, page.shape), 0, 255).astype(np.uint8)
    page = cv2.warpAffine(page, cv2.getRotationMatrix2D((PAGE_W / 2, PAGE_H / 2), 0, 1.0), (PAGE_W, PAGE_H), borderValue=255)
    ok, enc = cv2.imencode(".jpg", page, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(55, 85)])
    page = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE)
    return page, gt, ang
