"""Fine-tune the promoted reader (v3) on real Devanagari handwriting (IIIT-INDIC-HW-WORDS-Hindi).

- Starts from the v3 checkpoint, so the synthetic-trained knowledge is kept as the starting point.
- Low learning rate with a time-based cosine schedule (BUDGET_S seconds), CTC loss.
- Light augmentation (width jitter, ink thickness) on real words only.
- Model selection on the validation split; the test split is scored once at the end for v3 and the new model.

Env: BUDGET_S (seconds, default 3300), LR (3e-4), BATCH (32), OUT_DIR, PREP_DIR, THREADS (2).
"""
import json
import math
import os
import random
import sys
import time

import cv2
import numpy as np
import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/home/user/packages/model-adapters")
import htr_crnn as C  # noqa: E402

PREP = os.environ.get("PREP_DIR", os.path.expanduser("~/.cache/htr_raw/iiit_hindi/prepared"))
OUT = os.environ.get("OUT_DIR", "/home/user/ml/htr/results_real_v4")
CKPT_V3 = "/home/user/packages/model-adapters/models/htr_crnn_v3.pt"
BUDGET_S = float(os.environ.get("BUDGET_S", 3300))
LR = float(os.environ.get("LR", 3e-4))
BATCH = int(os.environ.get("BATCH", 32))
torch.set_num_threads(int(os.environ.get("THREADS", 2)))
torch.manual_seed(0)
rng = random.Random(0)
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "train_log.txt"), "a", buffering=1)


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG.write(line + "\n")


def load_split(name):
    y = json.load(open(os.path.join(PREP, f"{name}_y.json"), encoding="utf-8"))
    X = np.load(os.path.join(PREP, f"{name}_X.npy"), mmap_mode="r")
    return X, y


def encode(texts, charset):
    idx = {c: i + 1 for i, c in enumerate(charset)}
    flat, lens = [], []
    for t in texts:
        ids = [idx[c] for c in t]
        flat.extend(ids)
        lens.append(len(ids))
    return torch.tensor(flat, dtype=torch.long), torch.tensor(lens, dtype=torch.long)


def augment(img):
    # width jitter then re-centre on the 320-wide canvas
    s = rng.uniform(0.9, 1.1)
    w = max(8, int(round(img.shape[1] * s)))
    out = cv2.resize(img, (w, C.LINE_H), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((C.LINE_H, C.LINE_W), 255, np.uint8)
    n = min(out.shape[1], C.LINE_W)
    canvas[:, :n] = out[:, :n]
    # ink thickness jitter
    if rng.random() < 0.25:
        ink = 255 - canvas
        k = np.ones((2, 2), np.uint8)
        ink = cv2.erode(ink, k) if rng.random() < 0.5 else cv2.dilate(ink, k)
        canvas = 255 - ink
    return canvas


def batch_tensor(X, indices, aug=False):
    arr = np.stack([augment(np.asarray(X[i])) if aug else np.asarray(X[i]) for i in indices])
    x = torch.from_numpy(arr.astype(np.float32) / 127.5 - 1.0)[:, None]
    return x


def greedy_texts(model, X, charset, idxs, bs=128):
    model.eval()
    out = []
    with torch.no_grad():
        for s in range(0, len(idxs), bs):
            chunk = idxs[s:s + bs]
            logits = model(batch_tensor(X, chunk)).numpy()
            for lg in logits:
                text, _ = C.greedy_decode(lg, charset)
                out.append(text)
    return out


def score(hyps, refs):
    ed = sum(C.edit_distance(h, r) for h, r in zip(hyps, refs))
    chars = sum(len(r) for r in refs)
    wer = sum(h != r for h, r in zip(hyps, refs)) / max(1, len(refs))
    exact = sum(h == r for h, r in zip(hyps, refs)) / max(1, len(refs))
    return {"cer": round(ed / max(1, chars), 4), "word_error_rate": round(wer, 4), "exact_match": round(exact, 4),
            "words": len(refs)}


def main():
    ck = torch.load(CKPT_V3, map_location="cpu", weights_only=False)
    charset = ck["charset"]
    model = C.CRNN(len(charset), hidden=ck.get("hidden", 256))
    model.load_state_dict(ck["state_dict"])

    Xtr, ytr = load_split("train")
    Xva, yva = load_split("validation")
    Xte, yte = load_split("test")
    log(f"train {len(ytr)} validation {len(yva)} test {len(yte)} words; budget {BUDGET_S}s lr {LR} batch {BATCH}")

    # fixed evaluation subsets (deterministic)
    va_idx = list(range(0, len(yva), max(1, len(yva) // 1500)))[:1500]
    va_refs = [yva[i] for i in va_idx]

    # baseline on the full test split (v3, before any training)
    base_hyps = greedy_texts(model, Xte, charset, list(range(len(yte))))
    base_test = score(base_hyps, yte)
    log(f"baseline v3 test: {base_test}")

    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
    ctc = nn.CTCLoss(blank=0, zero_infinity=True)
    order = list(range(len(ytr)))
    best_val, best_step, step, t0 = float("inf"), 0, 0, time.time()
    hist = []
    epoch = 0
    done = False
    while not done:
        rng.shuffle(order)
        epoch += 1
        model.train()
        for s in range(0, len(order) - BATCH + 1, BATCH):
            elapsed = time.time() - t0
            if elapsed > BUDGET_S:
                done = True
                break
            lr = LR * 0.5 * (1 + math.cos(math.pi * elapsed / BUDGET_S))
            for g in opt.param_groups:
                g["lr"] = max(lr, LR * 0.02)
            idx = order[s:s + BATCH]
            x = batch_tensor(Xtr, idx, aug=True)
            targets, tlens = encode([ytr[i] for i in idx], charset)
            logits = model(x)                                  # (B, T, K+1)
            logp = logits.log_softmax(-1).permute(1, 0, 2)     # (T, B, K+1)
            ilens = torch.full((len(idx),), logp.shape[0], dtype=torch.long)
            loss = ctc(logp, targets, ilens, tlens)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            step += 1
            if step % 100 == 0:
                log(f"epoch {epoch} step {step} loss {loss.item():.3f} lr {lr:.2e} elapsed {int(elapsed)}s")
            if step % 600 == 0:
                val = score(greedy_texts(model, Xva, charset, va_idx), va_refs)
                hist.append({"step": step, "epoch": epoch, **val})
                log(f"VAL step {step}: {val}")
                if val["cer"] < best_val:
                    best_val, best_step = val["cer"], step
                    torch.save({"state_dict": model.state_dict(), "charset": charset, "hidden": ck.get("hidden", 256),
                                "line_h": C.LINE_H, "line_w": C.LINE_W}, os.path.join(OUT, "crnn_best.pt"))
                    log(f"saved best (val CER {best_val})")
        if done:
            break

    # final validation and save if it is the best so far
    val = score(greedy_texts(model, Xva, charset, va_idx), va_refs)
    hist.append({"step": step, "epoch": epoch, "final": True, **val})
    log(f"VAL final step {step}: {val}")
    if val["cer"] < best_val:
        best_val, best_step = val["cer"], step
        torch.save({"state_dict": model.state_dict(), "charset": charset, "hidden": ck.get("hidden", 256),
                    "line_h": C.LINE_H, "line_w": C.LINE_W}, os.path.join(OUT, "crnn_best.pt"))
    # score the saved best on the full test split
    best_ck = torch.load(os.path.join(OUT, "crnn_best.pt"), map_location="cpu", weights_only=False)
    best_model = C.CRNN(len(charset), hidden=ck.get("hidden", 256))
    best_model.load_state_dict(best_ck["state_dict"])
    new_test = score(greedy_texts(best_model, Xte, charset, list(range(len(yte)))), yte)
    report = {"baseline_v3_test": base_test, "finetuned_test": new_test, "best_val_cer": best_val,
              "best_step": best_step, "total_steps": step, "epochs_started": epoch, "budget_s": BUDGET_S,
              "lr": LR, "batch": BATCH, "history": hist, "train_words": len(ytr)}
    json.dump(report, open(os.path.join(OUT, "eval_report.json"), "w"), indent=2, ensure_ascii=False)
    log(f"REPORT baseline {base_test} -> finetuned {new_test}")


if __name__ == "__main__":
    main()
