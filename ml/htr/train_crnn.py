"""Train the CRNN-CTC line recogniser on synthetic handwritten-style lines (train split only).

Model selection uses the validation split (greedy character error rate). The test split is
never touched here. Epoch count is chosen from a measured batch time so the run fits the budget.
"""
import json
import os
import random
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn

import crnn
import htr_data as H

torch.set_num_threads(2)
torch.manual_seed(0)
random.seed(0)
BUDGET_S = float(os.environ.get("BUDGET_S", 1500))
N_TRAIN = int(os.environ.get("N_TRAIN", 14000))
N_VAL = int(os.environ.get("N_VAL", 600))
BATCH = int(os.environ.get("BATCH", 48))
HIDDEN = int(os.environ.get("HIDDEN", 128))          # LSTM width; 128 = original CPU model
MAX_EPOCHS = int(os.environ.get("MAX_EPOCHS", 14))
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("device", DEVICE, "hidden", HIDDEN, flush=True)
OUT = Path(os.environ.get("OUT_DIR", "/home/user/ml/htr/results"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("DATA_DIR", "/tmp/htr_data"))
DATA.mkdir(parents=True, exist_ok=True)

units = H.load_units()
train_units = [(q, t) for q, t in units if H.split_of(q) == "train"]
val_units = [(q, t) for q, t in units if H.split_of(q) == "val"]

# ---- training lines: several random re-chunkings of the train split, rendered with random strength
t0 = time.time()
train_pairs = []
s = 0
while len(train_pairs) < N_TRAIN:
    for q, text in H.chunk_units(train_units, seed=100 + s):
        train_pairs.append((q, text))
    s += 1
random.Random(1).shuffle(train_pairs)
train_pairs = train_pairs[:N_TRAIN]
val_pairs = H.chunk_units(val_units, seed=5)[:N_VAL]
charset = H.charset([t for _, t in train_pairs] + [t for _, t in val_pairs])
c2i = {c: i + 1 for i, c in enumerate(charset)}
print("charset", len(charset), "train", len(train_pairs), "val", len(val_pairs), flush=True)

def page_like(arr, rng):
    """Page-scan degradation applied at native resolution: small rotation, lighting, noise, JPEG,
    and random white margins so training crops resemble the detected page crops."""
    h, w = arr.shape
    if rng.random() < 0.7:
        M = cv2.getRotationMatrix2D((w / 2, h / 2), rng.uniform(-1.5, 1.5), 1.0)
        arr = cv2.warpAffine(arr, M, (w, h), borderValue=255)
    if rng.random() < 0.7:
        grad = np.linspace(rng.uniform(0.8, 1.0), rng.uniform(0.8, 1.0), w)[None, :]
        noise = np.random.default_rng(rng.randint(0, 2**31)).normal(0, rng.uniform(2, 8), arr.shape)
        arr = np.clip(arr.astype(np.float32) * grad + noise, 0, 255).astype(np.uint8)
    if rng.random() < 0.6:
        ok, enc = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(50, 90)])
        arr = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE)
    t, b, l, r = (rng.randint(0, 10) for _ in range(4))
    return cv2.copyMakeBorder(arr, t, b, l, r, cv2.BORDER_CONSTANT, value=255)


def synth_line_v2(text, rng, strength=1.0):
    img = H.render_text(text, rng, size=rng.choice([26, 30, 34]))
    img = H.handwrite(img, rng, strength)
    if rng.random() < 0.85:
        img = page_like(img, rng)
    return H.to_network(img)


rng = random.Random(2)
X = np.zeros((len(train_pairs), H.LINE_H, H.LINE_W), np.uint8)
for i, (_, text) in enumerate(train_pairs):
    X[i] = synth_line_v2(text, rng, strength=rng.uniform(0.6, 1.4))
Xv = np.stack([synth_line_v2(t, random.Random(9 + i), strength=1.0) for i, (_, t) in enumerate(val_pairs)])
print("rendered in", round(time.time() - t0, 1), "s", flush=True)

model = crnn.CRNN(len(charset), hidden=HIDDEN).to(DEVICE)
print("params", sum(p.numel() for p in model.parameters()), flush=True)
ctc = nn.CTCLoss(blank=0, zero_infinity=True)
opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)


def batch_tensors(idx, Xs, texts):
    x = torch.from_numpy(Xs[idx].astype(np.float32) / 127.5 - 1.0)[:, None].to(DEVICE)
    labels = [torch.tensor([c2i[c] for c in texts[i]], dtype=torch.long) for i in idx]
    lens = torch.tensor([len(l) for l in labels], dtype=torch.long)
    return x, torch.cat(labels).to(DEVICE), lens.to(DEVICE)


train_texts = [t for _, t in train_pairs]
val_texts = [t for _, t in val_pairs]

# ---- measure speed to choose epochs for the budget
model.train()
idx = np.arange(BATCH)
ts = time.time()
for _ in range(3):
    x, y, yl = batch_tensors(idx, X, train_texts)
    out = model(x).log_softmax(-1).permute(1, 0, 2)
    loss = ctc(out, y, torch.full((BATCH,), out.shape[0], dtype=torch.long, device=DEVICE), yl)
    opt.zero_grad(); loss.backward(); opt.step()
per_batch = (time.time() - ts) / 3
steps_per_epoch = len(train_pairs) // BATCH
epoch_s = per_batch * steps_per_epoch + 20  # plus validation
EPOCHS = int(max(3, min(MAX_EPOCHS, BUDGET_S // epoch_s)))
print(f"batch {per_batch:.2f}s, epoch ~{epoch_s:.0f}s, epochs chosen {EPOCHS}", flush=True)
model = crnn.CRNN(len(charset), hidden=HIDDEN).to(DEVICE)  # reset weights after timing steps
opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=2e-3, total_steps=EPOCHS * steps_per_epoch, pct_start=0.15)


def val_cer():
    model.eval()
    errs, total = 0, 0
    with torch.no_grad():
        for i in range(0, len(Xv), 100):
            x = torch.from_numpy(Xv[i:i + 100].astype(np.float32) / 127.5 - 1.0)[:, None].to(DEVICE)
            logits = model(x).cpu().numpy()
            for j in range(logits.shape[0]):
                pred, _ = crnn.greedy_decode(logits[j], charset)
                ref = val_texts[i + j]
                errs += crnn.edit_distance(pred, ref)
                total += len(ref)
    model.train()
    return errs / max(1, total)


log, best = [], 1e9
t_start = time.time()
for ep in range(1, EPOCHS + 1):
    perm = np.random.default_rng(ep).permutation(len(train_pairs))
    run_loss, n = 0.0, 0
    for b in range(steps_per_epoch):
        idx = perm[b * BATCH:(b + 1) * BATCH]
        x, y, yl = batch_tensors(idx, X, train_texts)
        out = model(x).log_softmax(-1).permute(1, 0, 2)
        loss = ctc(out, y, torch.full((len(idx),), out.shape[0], dtype=torch.long, device=DEVICE), yl)
        opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        opt.step(); sched.step()
        run_loss += loss.item(); n += 1
    cer = val_cer()
    rec = {"epoch": ep, "train_ctc": round(run_loss / n, 4), "val_cer": round(cer, 4),
           "seconds": round(time.time() - t_start, 1)}
    log.append(rec)
    print(json.dumps(rec), flush=True)
    if cer < best:
        best = cer
        torch.save({"state_dict": {k: v.cpu() for k, v in model.state_dict().items()}, "charset": charset, "hidden": HIDDEN,
                    "line_h": H.LINE_H, "line_w": H.LINE_W}, OUT / "crnn_best.pt")
    if time.time() - t0 > BUDGET_S + 600:
        print("hard stop on time", flush=True)
        break

(OUT / "train_log.json").write_text(json.dumps({"epochs": log, "best_val_cer": best, "charset_size": len(charset),
                                                  "n_train_lines": len(train_pairs), "n_val_lines": len(val_pairs),
                                                  "batch": BATCH, "lr": 2e-3}, indent=2, ensure_ascii=False))
print("done best val CER", round(best, 4), flush=True)
