"""Pipeline tuning and evaluation.

1. Grid-search pipeline options on VALIDATION copies (deskew, binarisation, rule removal).
2. Choose the review-flag confidence threshold on validation (maximise F1 for catching wrong lines).
3. Score the chosen configuration ONCE on TEST copies, and report speed and model size.
4. Compare fp32 with dynamic int8 quantisation for the recogniser (accuracy, latency, size).
"""
import itertools
import json
import os
import time
from pathlib import Path

import cv2
import numpy as np
import torch

import crnn
import pipeline as P

RES = Path(os.environ.get("HTR_RES", "/home/user/ml/htr/results"))
PAGES = Path("/tmp/htr_pages")
meta = json.loads((RES / "copies_meta.json").read_text())
CKPT = RES / "crnn_best.pt"
torch.set_num_threads(2)


def load_pages(split):
    out = []
    for c in meta[split]:
        img = cv2.imread(str(PAGES / split / c["file"]), cv2.IMREAD_GRAYSCALE)
        out.append((c["file"], img, [tuple(x) for x in c["gt_lines"]]))
    return out


def run_config(model, charset, pages, cfg, tau):
    agg = {"char_err": 0, "char_tot": 0, "word_err": 0, "word_tot": 0, "gt": 0, "matched": 0,
           "spurious": 0, "flagged": 0, "flagged_err": 0, "unflagged_err": 0, "unflagged": 0,
           "time": 0.0, "pages": 0, "tp": 0, "fp": 0, "fn": 0}
    for name, img, gt in pages:
        res = P.recognise(img, cfg, model, charset)
        s = P.score_page(res, gt, tau)
        agg["pages"] += 1
        agg["time"] += res.timings.get("total_s", 0.0)
        agg["gt"] += s["gt_lines"]; agg["matched"] += s["matched_lines"]; agg["spurious"] += s["spurious_segments"]
        pairs, _ = P.match_to_gt(res.segments, gt)
        for gi, si in pairs:
            ref = gt[gi][0]
            pred = "" if si is None else res.segments[si].text
            wrong = crnn.edit_distance(pred, ref) > 0
            flag = True if si is None else res.segments[si].conf < tau
            agg["tp"] += int(flag and wrong); agg["fp"] += int(flag and not wrong); agg["fn"] += int((not flag) and wrong)
        agg["char_err"] += s["cer"] * sum(len(g[0]) for g in gt)
        agg["char_tot"] += sum(len(g[0]) for g in gt)
        agg["word_err"] += s["wer"] * sum(len(g[0].split()) for g in gt)
        agg["word_tot"] += sum(len(g[0].split()) for g in gt)
    f1 = 2 * agg["tp"] / max(1, 2 * agg["tp"] + agg["fp"] + agg["fn"])
    return {
        "cer": round(agg["char_err"] / agg["char_tot"], 4),
        "wer": round(agg["word_err"] / agg["word_tot"], 4),
        "line_recall": round(agg["matched"] / agg["gt"], 4),
        "spurious_segments": agg["spurious"],
        "review_flag_f1": round(f1, 4),
        "review_precision": round(agg["tp"] / max(1, agg["tp"] + agg["fp"]), 4),
        "review_recall": round(agg["tp"] / max(1, agg["tp"] + agg["fn"]), 4),
        "sec_per_page": round(agg["time"] / agg["pages"], 3),
    }, agg


def tau_sweep(model, charset, pages, cfg, lo=0.30, hi=0.995, step=0.005):
    """Choose the review-flag threshold on validation. Each page is recognised once; every tau is then
    scored from the cached (confidence, wrong) pairs. Missing lines always count as flagged."""
    items = []  # (conf or None if missing, is_wrong)
    for name, img, gt in pages:
        res = P.recognise(img, cfg, model, charset)
        pairs, _ = P.match_to_gt(res.segments, gt)
        for gi, si in pairs:
            ref = gt[gi][0]
            if si is None:
                items.append((None, True))
            else:
                items.append((res.segments[si].conf, crnn.edit_distance(res.segments[si].text, ref) > 0))
    rows, best = [], None
    for tau in np.arange(lo, hi + 1e-9, step):
        tp = fp = fn = 0
        for conf, wrong in items:
            flag = True if conf is None else conf < tau
            tp += int(flag and wrong); fp += int(flag and not wrong); fn += int((not flag) and wrong)
        f1 = 2 * tp / max(1, 2 * tp + fp + fn)
        rows.append({"tau": round(float(tau), 3), "review_flag_f1": round(f1, 4),
                     "review_precision": round(tp / max(1, tp + fp), 4), "review_recall": round(tp / max(1, tp + fn), 4)})
        if best is None or f1 > best[1]:
            best = (round(float(tau), 3), f1)
    return best[0], rows


def main():
    model, charset = crnn.load_checkpoint(CKPT)
    val_pages = load_pages("val")
    test_pages = load_pages("test")
    report = {"model": {"file": CKPT.name, "params": sum(p.numel() for p in model.parameters()),
                        "fp32_mb": round(CKPT.stat().st_size / 1e6, 2), "charset": len(charset)}}

    # 1. grid on validation (tau fixed at the default while comparing preprocessing)
    grid = []
    for ds, bn, rr, ink, pad, pthr in itertools.product(
            [False, True], ["none", "clahe"], [False, True], [0, 200], [10, 12, 14, 16], [0.02, 0.05]):
        cfg = P.Config(deskew=ds, binarise=bn, remove_rules=rr, ink_thr=ink, pad=pad, profile_thr=pthr)
        m, _ = run_config(model, charset, val_pages, cfg, cfg.conf_flag)
        grid.append({"deskew": ds, "binarise": bn, "remove_rules": rr, "ink_thr": ink, "pad": pad,
                     "profile_thr": pthr, **m})
        print("val", ds, bn, rr, ink, pad, pthr, m["cer"], m["wer"], flush=True)
    grid.sort(key=lambda r: (r["cer"], r["sec_per_page"]))
    report["validation_grid"] = grid
    best = grid[0]
    cfg = P.Config(deskew=best["deskew"], binarise=best["binarise"], remove_rules=best["remove_rules"],
                   ink_thr=best["ink_thr"], pad=best["pad"], profile_thr=best["profile_thr"])

    # 2. review-flag threshold on validation
    tau, tau_rows = tau_sweep(model, charset, val_pages, cfg)
    cfg.conf_flag = tau
    report["validation_tau_sweep"] = tau_rows
    report["chosen_config"] = {"deskew": cfg.deskew, "binarise": cfg.binarise, "remove_rules": cfg.remove_rules,
                               "ink_thr": cfg.ink_thr, "pad": cfg.pad, "profile_thr": cfg.profile_thr,
                               "conf_flag": round(tau, 2)}

    # 3. test, once
    test_metrics, _ = run_config(model, charset, test_pages, cfg, tau)
    report["test_chosen_config"] = test_metrics
    print("TEST", test_metrics, flush=True)

    # 4. quantised recogniser (dynamic int8 on LSTM and Linear)
    import copy
    qm = torch.ao.quantization.quantize_dynamic(copy.deepcopy(model), {torch.nn.LSTM, torch.nn.Linear}, dtype=torch.qint8)
    qm.eval()
    torch.save({"state_dict": qm.state_dict(), "charset": charset, "hidden": 128}, RES / "crnn_int8_state.pt")
    q_metrics, _ = run_config(qm, charset, test_pages, cfg, tau)
    report["test_int8"] = q_metrics
    report["model"]["int8_mb"] = round((RES / "crnn_int8_state.pt").stat().st_size / 1e6, 2)
    print("TEST int8", q_metrics, flush=True)

    # 5. per-copy results on test for the chosen fp32 config
    per_copy = []
    for name, img, gt in test_pages:
        res = P.recognise(img, cfg, model, charset)
        s = P.score_page(res, gt, tau)
        per_copy.append({"copy": name, "cer": round(s["cer"], 4), "wer": round(s["wer"], 4),
                         "line_recall": round(s["line_recall"], 4), "flagged_lines": s["flagged_lines"],
                         "skew_deg": round(res.timings.get("deskew_deg", 0.0), 2)})
    report["test_per_copy"] = per_copy
    (RES / "eval_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print("saved eval_report.json", flush=True)


if __name__ == "__main__":
    main()
