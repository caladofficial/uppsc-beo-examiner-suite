"""Score checkpoints on the 12 regenerated synthetic test pages with the PACKAGED reader (wide-line split on)."""
import json, sys
from pathlib import Path
import cv2
sys.path.insert(0, "/home/user/packages/model-adapters")
import htr_crnn as crnn
import htr_pipeline as HP
sys.path.insert(0, "/home/user/ml/htr")
import pipeline as P  # score_page / match_to_gt only

meta = json.loads(Path("/tmp/htr_regen/copies_meta.json").read_text())
pages = []
for c in meta["test"]:
    img = cv2.imread(f"/tmp/htr_pages/test/{c['file']}", cv2.IMREAD_GRAYSCALE)
    pages.append((img, [tuple(x) for x in c["gt_lines"]]))

def bench(ckpt):
    model, charset = crnn.load_checkpoint(ckpt)
    model.eval()
    cfg = HP.Config()
    tot = {"ce": 0, "ct": 0, "we": 0, "wt": 0, "gt": 0, "matched": 0, "flag": 0, "spur": 0}
    for img, gt in pages:
        res = HP.recognise(img, cfg, model, charset)
        s = P.score_page(res, gt, cfg.conf_flag)
        tot["ce"] += s["cer"] * sum(len(g[0]) for g in gt); tot["ct"] += sum(len(g[0]) for g in gt)
        tot["we"] += s["wer"] * sum(len(g[0].split()) for g in gt); tot["wt"] += sum(len(g[0].split()) for g in gt)
        tot["gt"] += s["gt_lines"]; tot["matched"] += s["matched_lines"]; tot["spur"] += s["spurious_segments"]
        tot["flag"] += sum(1 for x in res.segments if x.flagged)
    n = len(pages)
    return {"cer": round(tot["ce"] / tot["ct"], 4), "wer": round(tot["we"] / tot["wt"], 4),
            "line_recall": round(tot["matched"] / tot["gt"], 4), "flagged_per_page": round(tot["flag"] / n, 2),
            "spurious": tot["spur"]}

if __name__ == "__main__":
    out = {}
    for name, path in [a.split("=", 1) for a in sys.argv[1:]]:
        out[name] = bench(path)
        print(name, out[name], flush=True)
    Path("/tmp/htr_regen/page_bench.json").write_text(json.dumps(out, indent=1))
