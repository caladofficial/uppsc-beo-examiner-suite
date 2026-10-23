"""Prepare IIIT-INDIC-HW-WORDS-Hindi (CC BY 4.0; Gongidi & Jawahar, ICDAR 2021) for the line reader.

Each word image is cropped to its ink, scaled to the reader's input height (40 px) and left-aligned on a
40 x 320 white canvas, the same layout the reader sees at inference. Labels containing characters the
checkpoint cannot output are dropped and counted; nothing is guessed.

Output (outside the workspace, large): <OUT>/<split>_X.npy (uint8 memmap, N x 40 x 320) and <split>_y.json.
"""
import glob
import json
import os
import sys
import unicodedata

import cv2
import numpy as np
import pyarrow.parquet as pq
import torch

SRC = os.environ.get("IIIT_DIR", os.path.expanduser("~/.cache/htr_raw/iiit_hindi"))
OUT = os.environ.get("PREP_DIR", os.path.expanduser("~/.cache/htr_raw/iiit_hindi/prepared"))
CKPT = os.environ.get("CKPT", "/home/user/packages/model-adapters/models/htr_crnn_v3.pt")
LINE_H, LINE_W = 40, 320
PAD = 4
os.makedirs(OUT, exist_ok=True)

charset = set(torch.load(CKPT, map_location="cpu", weights_only=False)["charset"])

SPLITS = {
    "train": sorted(glob.glob(os.path.join(SRC, "train-*.parquet"))),
    "validation": [os.path.join(SRC, "validation-00000-of-00001.parquet")],
    "test": [os.path.join(SRC, "test-00000-of-00001.parquet")],
}


def normalise_word(img_bytes):
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    # scanned form cells have a grey background; stretch it to white so it matches clean line images
    bg = float(np.percentile(img, 90))
    img = np.clip(img.astype(np.float32) * 255.0 / max(bg, 1.0), 0, 255).astype(np.uint8)
    _, ink = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ys, xs = np.where(ink > 0)
    if ys.size:
        y0, y1 = max(0, ys.min() - PAD), min(img.shape[0], ys.max() + PAD + 1)
        x0, x1 = max(0, xs.min() - PAD), min(img.shape[1], xs.max() + PAD + 1)
        img = img[y0:y1, x0:x1]
    h, w = img.shape
    nw = max(8, int(round(w * LINE_H / h)))
    img = cv2.resize(img, (nw, LINE_H), interpolation=cv2.INTER_AREA)
    canvas = np.full((LINE_H, LINE_W), 255, np.uint8)
    if nw > LINE_W:  # very long word: squeeze to fit; counted by the caller
        return cv2.resize(img, (LINE_W, LINE_H), interpolation=cv2.INTER_AREA), True
    canvas[:, :nw] = img
    return canvas, False


def run():
    stats = {}
    for split, files in SPLITS.items():
        rows_total = sum(pq.ParquetFile(f).metadata.num_rows for f in files)
        X = np.lib.format.open_memmap(os.path.join(OUT, f"{split}_X.npy"), mode="w+",
                                      dtype=np.uint8, shape=(rows_total, LINE_H, LINE_W))
        labels, kept, dropped_oov, squeezed, bad = [], 0, 0, 0, 0
        for f in files:
            pf = pq.ParquetFile(f)
            for batch in pf.iter_batches(batch_size=256, columns=["image", "text"]):
                for r in batch.to_pylist():
                    text = unicodedata.normalize("NFC", (r["text"] or "").strip())
                    if not text:
                        bad += 1
                        continue
                    if any(ch not in charset for ch in text):
                        dropped_oov += 1
                        continue
                    res = normalise_word(r["image"]["bytes"])
                    if res is None:
                        bad += 1
                        continue
                    img, was_squeezed = res
                    squeezed += int(was_squeezed)
                    X[kept] = img
                    labels.append(text)
                    kept += 1
            print(f"{split}: {os.path.basename(f)} done, kept {kept}", flush=True)
        X.flush()
        del X  # the first len(labels) rows of the memmap are valid; the loader uses that count
        with open(os.path.join(OUT, f"{split}_y.json"), "w", encoding="utf-8") as fh:
            json.dump(labels, fh, ensure_ascii=False)
        stats[split] = {"kept": kept, "allocated_rows": rows_total, "dropped_out_of_charset": dropped_oov, "squeezed_long_words": squeezed,
                        "bad_or_empty": bad, "rows_in_source": rows_total}
        print(split, stats[split], flush=True)
    with open(os.path.join(OUT, "prep_stats.json"), "w") as fh:
        json.dump(stats, fh, indent=2)


if __name__ == "__main__":
    run()
