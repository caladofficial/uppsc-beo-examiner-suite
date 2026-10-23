"""Mixed fine-tune of the promoted reader (v3) on real Devanagari handwriting, keeping line-level skill.

Why mixed: a word-only fine-tune (finetune_real.py) fixed single real words but broke line reading
(synthetic-page line CER 0.020 -> 0.856). So every batch is half real-handwriting lines and half
synthetic lines:
- real lines: 2-3 real word crops (IIIT-INDIC-HW-WORDS-Hindi, CC BY 4.0) joined left to right with the
  true transcripts, so the model sees real strokes in line-length images;
- synthetic lines: the same generator and charset as the v3 training (htr_data), so line skill is kept.

Checkpoint selection: best mean of synthetic-val CER and real-line-val CER, accepted only while the
synthetic-val CER stays at or below SYN_GUARD (the v3 model's own level is about 0.02).
"""
import json
import math
import os
import random
import sys
import time
import unicodedata

import cv2
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, "/home/user/packages/model-adapters")
sys.path.insert(0, "/home/user/ml/htr")
import htr_crnn as C  # noqa: E402
import htr_data as H  # noqa: E402

PREP = os.environ.get("PREP_DIR", os.path.expanduser("~/.cache/htr_raw/iiit_hindi/prepared"))
OUT = os.environ.get("OUT_DIR", "/home/user/ml/htr/results_mixed_v4")
CKPT_V3 = "/home/user/packages/model-adapters/models/htr_crnn_v3.pt"
BUDGET_S = float(os.environ.get("BUDGET_S", 3000))
LR = float(os.environ.get("LR", 2e-4))
BATCH = int(os.environ.get("BATCH", 32))
N_SYN = int(os.environ.get("N_SYN", 12000))
SYN_GUARD_REL = float(os.environ.get("SYN_GUARD_REL", 1.25))  # synthetic val CER may rise at most 25% over v3
REAL_FRAC = float(os.environ.get("REAL_FRAC", 0.5))
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


def ink_crop(img):
    cols = np.where((img < 128).any(axis=0))[0]
    if cols.size == 0:
        return img[:, :8]
    return img[:, max(0, cols[0] - 2): cols[-1] + 3]


def compose_line(X, y, idxs, gap=10):
    """Join word crops left to right into one 40 x 320 real-handwriting line."""
    parts, texts, width = [], [], 0
    for i in idxs:
        crop = ink_crop(np.asarray(X[i]))
        w = crop.shape[1] + (gap if parts else 0)
        if width + w > C.LINE_W - 2:
            break
        if parts:
            parts.append(np.full((C.LINE_H, gap), 255, np.uint8))
        parts.append(crop)
        texts.append(y[i])
        width += w
    canvas = np.full((C.LINE_H, C.LINE_W), 255, np.uint8)
    if parts:
        line = np.hstack(parts)
        canvas[:, :line.shape[1]] = line
    return canvas, " ".join(texts)


def real_line_batch(X, y, n, r):
    imgs, texts = [], []
    for _ in range(n):
        k = r.choice([2, 2, 3])
        start = r.randrange(0, len(y) - k)
        idxs = list(range(start, start + k))  # consecutive words from the shuffled split order
        img, t = compose_line(X, y, idxs)
        if t:
            imgs.append(img)
            texts.append(t)
    return imgs, texts


def page_like(arr, r):
    """Page-scan degradation, copied from ml/htr/train_crnn.py so synthetic lines match the v3 training."""
    h, w = arr.shape
    if r.random() < 0.7:
        M = cv2.getRotationMatrix2D((w / 2, h / 2), r.uniform(-1.5, 1.5), 1.0)
        arr = cv2.warpAffine(arr, M, (w, h), borderValue=255)
    if r.random() < 0.7:
        grad = np.linspace(r.uniform(0.8, 1.0), r.uniform(0.8, 1.0), w)[None, :]
        noise = np.random.default_rng(r.randint(0, 2**31)).normal(0, r.uniform(2, 8), arr.shape)
        arr = np.clip(arr.astype(np.float32) * grad + noise, 0, 255).astype(np.uint8)
    if r.random() < 0.6:
        ok, enc = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, r.randint(50, 90)])
        arr = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE)
    t, b, l, rr = (r.randint(0, 10) for _ in range(4))
    return cv2.copyMakeBorder(arr, t, b, l, rr, cv2.BORDER_CONSTANT, value=255)


def synth_bank(split_units, seed, n):
    chunks = []
    s = 0
    while len(chunks) < n:
        for q, text in H.chunk_units(split_units, seed=seed + s):
            chunks.append(text)
        s += 1
    chunks = chunks[:n]
    r = random.Random(seed)
    imgs = []
    for i, t in enumerate(chunks):
        img = H.render_text(t, r, size=r.choice([26, 30, 34]))
        img = H.handwrite(img, r, r.uniform(0.6, 1.4))
        if r.random() < 0.85:
            img = page_like(img, r)
        imgs.append(H.to_network(img))
    return np.stack(imgs), chunks


def augment(img):
    s = rng.uniform(0.9, 1.1)
    w = max(8, int(round(img.shape[1] * s)))
    out = cv2.resize(img, (w, C.LINE_H), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((C.LINE_H, C.LINE_W), 255, np.uint8)
    n = min(out.shape[1], C.LINE_W)
    canvas[:, :n] = out[:, :n]
    if rng.random() < 0.25:
        ink = 255 - canvas
        k = np.ones((2, 2), np.uint8)
        ink = cv2.erode(ink, k) if rng.random() < 0.5 else cv2.dilate(ink, k)
        canvas = 255 - ink
    return canvas


def to_x(arr):
    return torch.from_numpy(np.stack(arr).astype(np.float32) / 127.5 - 1.0)[:, None]


def encode(texts, cidx):
    flat, lens = [], []
    for t in texts:
        ids = [cidx[c] for c in t if c in cidx]
        flat.extend(ids)
        lens.append(len(ids))
    return torch.tensor(flat, dtype=torch.long), torch.tensor(lens, dtype=torch.long)


def decode_all(model, arrays, charset, bs=128):
    model.eval()
    out = []
    with torch.no_grad():
        for s in range(0, len(arrays), bs):
            logits = model(to_x(arrays[s:s + bs])).numpy()
            for lg in logits:
                out.append(C.greedy_decode(lg, charset)[0])
    return out


def cer(hyps, refs):
    ed = sum(C.edit_distance(h, r) for h, r in zip(hyps, refs))
    return round(ed / max(1, sum(len(r) for r in refs)), 4)


def main():
    ck = torch.load(CKPT_V3, map_location="cpu", weights_only=False)
    charset = ck["charset"]
    cidx = {c: i + 1 for i, c in enumerate(charset)}
    model = C.CRNN(len(charset), hidden=ck.get("hidden", 256))
    model.load_state_dict(ck["state_dict"])  # v3 reference weights
    init_path = os.environ.get("INIT", "")
    if init_path:
        model.load_state_dict(torch.load(init_path, map_location="cpu", weights_only=False)["state_dict"])
        log(f"starting from {init_path}")
    v3_ref = C.CRNN(len(charset), hidden=ck.get("hidden", 256))
    v3_ref.load_state_dict(ck["state_dict"])

    units = H.load_units()
    tr_units = [(q, t) for q, t in units if H.split_of(q) == "train"]
    va_units = [(q, t) for q, t in units if H.split_of(q) == "val"]
    t0 = time.time()
    syn_tr_imgs, syn_tr_txt = synth_bank(tr_units, seed=100, n=N_SYN)
    syn_va_imgs, syn_va_txt = synth_bank(va_units, seed=5, n=300)
    log(f"synthetic bank: train {len(syn_tr_txt)} val {len(syn_va_txt)} in {time.time() - t0:.0f}s")

    Xtr, ytr = load_split("train")
    Xva, yva = load_split("validation")
    Xte, yte = load_split("test")
    log(f"real words: train {len(ytr)} val {len(yva)} test {len(yte)}; budget {BUDGET_S}s lr {LR} batch {BATCH}")

    # fixed validation line set from real validation words
    rv = random.Random(11)
    va_real_imgs, va_real_txt = real_line_batch(Xva, yva, 300, rv)

    def evaluate(m):
        syn = cer(decode_all(m, list(syn_va_imgs), charset), syn_va_txt)
        real = cer(decode_all(m, va_real_imgs, charset), va_real_txt)
        return {"synthetic_val_cer": syn, "real_line_val_cer": real}

    base = evaluate(v3_ref)
    log(f"baseline v3 on validation: {base}")
    syn_guard_abs = base["synthetic_val_cer"] * SYN_GUARD_REL
    log(f"synthetic guard: <= {syn_guard_abs:.4f} (v3 {base['synthetic_val_cer']} x {SYN_GUARD_REL})")

    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
    ctc = nn.CTCLoss(blank=0, zero_infinity=True)
    half = max(1, int(round(BATCH * REAL_FRAC)))
    best_score, best_step, step, hist = float("inf"), 0, 0, []
    t_start = time.time()
    done = False
    while not done:
        model.train()
        for _ in range(10 ** 9):
            elapsed = time.time() - t_start
            if elapsed > BUDGET_S:
                done = True
                break
            lr = LR * 0.5 * (1 + math.cos(math.pi * elapsed / BUDGET_S))
            for g in opt.param_groups:
                g["lr"] = max(lr, LR * 0.02)
            real_imgs, real_txt = real_line_batch(Xtr, ytr, half, rng)
            syn_idx = [rng.randrange(len(syn_tr_txt)) for _ in range(BATCH - half)]
            imgs = [augment(im) for im in real_imgs] + [syn_tr_imgs[i] for i in syn_idx]
            texts = real_txt + [syn_tr_txt[i] for i in syn_idx]
            x = to_x(imgs)
            targets, tlens = encode(texts, cidx)
            logp = model(x).log_softmax(-1).permute(1, 0, 2)
            ilens = torch.full((len(texts),), logp.shape[0], dtype=torch.long)
            loss = ctc(logp, targets, ilens, tlens)
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            step += 1
            if step % 100 == 0:
                log(f"step {step} loss {loss.item():.3f} lr {lr:.2e} elapsed {int(elapsed)}s")
            if step % 500 == 0:
                v = evaluate(model)
                score = (v["synthetic_val_cer"] + v["real_line_val_cer"]) / 2
                hist.append({"step": step, **v})
                ok = v["synthetic_val_cer"] <= syn_guard_abs
                log(f"VAL step {step}: {v} score {score:.4f} guard_ok {ok}")
                if ok and score < best_score:
                    best_score, best_step = score, step
                    torch.save({"state_dict": model.state_dict(), "charset": charset,
                                "hidden": ck.get("hidden", 256), "line_h": C.LINE_H, "line_w": C.LINE_W},
                               os.path.join(OUT, "crnn_best.pt"))
                    log(f"saved best at step {step}")
                model.train()
    v = evaluate(model)
    score = (v["synthetic_val_cer"] + v["real_line_val_cer"]) / 2
    hist.append({"step": step, "final": True, **v})
    log(f"VAL final step {step}: {v} score {score:.4f}")
    if v["synthetic_val_cer"] <= syn_guard_abs and score < best_score:
        best_score, best_step = score, step
        torch.save({"state_dict": model.state_dict(), "charset": charset, "hidden": ck.get("hidden", 256),
                    "line_h": C.LINE_H, "line_w": C.LINE_W}, os.path.join(OUT, "crnn_best.pt"))
        log(f"saved final as best at step {step}")

    # always keep the final weights; test the best checkpoint if one passed the guard, else the final one
    torch.save({"state_dict": model.state_dict(), "charset": charset, "hidden": ck.get("hidden", 256),
                "line_h": C.LINE_H, "line_w": C.LINE_W}, os.path.join(OUT, "crnn_last.pt"))
    best_path = os.path.join(OUT, "crnn_best.pt")
    chosen = best_path if os.path.exists(best_path) else os.path.join(OUT, "crnn_last.pt")
    log(f"testing {os.path.basename(chosen)}")
    best = C.CRNN(len(charset), hidden=ck.get("hidden", 256))
    best.load_state_dict(torch.load(chosen, map_location="cpu", weights_only=False)["state_dict"])
    base_model = C.CRNN(len(charset), hidden=ck.get("hidden", 256))
    base_model.load_state_dict(ck["state_dict"])
    rt = random.Random(23)
    te_real_imgs, te_real_txt = real_line_batch(Xte, yte, 600, rt)
    te_syn_imgs, te_syn_txt = synth_bank(va_units, seed=77, n=300)

    def test_metrics(m):
        word_hyps = decode_all(m, [np.asarray(Xte[i]) for i in range(len(yte))], charset)
        return {
            "real_word_cer": cer(word_hyps, yte),
            "real_word_exact": round(sum(h == r for h, r in zip(word_hyps, yte)) / len(yte), 4),
            "real_line_cer": cer(decode_all(m, te_real_imgs, charset), te_real_txt),
            "synthetic_line_cer": cer(decode_all(m, list(te_syn_imgs), charset), te_syn_txt),
        }

    report = {
        "v3_promoted": test_metrics(base_model),
        "v4_mixed": test_metrics(best),
        "tested_checkpoint": os.path.basename(chosen), "best_step": best_step, "total_steps": step, "budget_s": BUDGET_S, "lr": LR, "batch": BATCH,
        "syn_guard_abs": syn_guard_abs, "syn_guard_rel": SYN_GUARD_REL, "real_frac": REAL_FRAC,
        "init": init_path or "v3", "history": hist,
    }
    json.dump(report, open(os.path.join(OUT, "eval_report.json"), "w"), indent=2, ensure_ascii=False)
    log(f"REPORT {json.dumps({k: report[k] for k in ('v3_promoted', 'v4_mixed')}, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
