"""Generate synthetic answer-page copies with exact ground truth for validation and test.

Validation copies come from validation questions, test copies from test questions. The two sets
share no question, so the test split is never seen during training or configuration tuning.
"""
import json
import random
from pathlib import Path

import cv2

import htr_data as H

OUT = Path("/tmp/htr_pages")
META = Path("/home/user/ml/htr/results/copies_meta.json")
PER_PAGE = 22
N = {"val": 6, "test": 12}
units = H.load_units()
meta = {}
for split, n_copies in N.items():
    lines = H.chunk_units([(q, t) for q, t in units if H.split_of(q) == split], seed=900 + len(split))
    random.Random(31).shuffle(lines)
    d = OUT / split
    d.mkdir(parents=True, exist_ok=True)
    meta[split] = []
    for c in range(n_copies):
        chunk = lines[c * PER_PAGE:(c + 1) * PER_PAGE]
        if len(chunk) < 8:
            break
        strength = [0.8, 1.0, 1.2][c % 3]
        page, gt, skew = H.make_copy([t for _, t in chunk], seed=1000 * (1 if split == 'val' else 2) + c, strength=strength)
        name = f"{split}_copy_{c:02d}.jpg"
        cv2.imwrite(str(d / name), page, [cv2.IMWRITE_JPEG_QUALITY, 95])
        meta[split].append({"file": name, "strength": strength, "skew_deg": round(skew, 2),
                            "questions": sorted({q for q, _ in chunk}),
                            "gt_lines": [[t, y0, y1] for t, y0, y1 in gt]})
META.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
for s in meta:
    print(s, len(meta[s]), "copies", sum(len(c['gt_lines']) for c in meta[s]), "lines")
