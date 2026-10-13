"""Devanagari handwritten character recognizer (HTR component) for the UPPSC grader.

Trains on Kaggle GPU using the public dataset `ashokpant/devanagari-character-dataset`
(NHCD handwritten vowels, consonants and numerals). Model selection uses the validation
split only; the test split is scored once with the selected checkpoint.
Outputs are written to /kaggle/working.
"""
import json
import os
import random
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from sklearn.metrics import confusion_matrix, f1_score
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

SEED = 1234
EPOCHS = int(os.environ.get("EPOCHS", 12))
TIME_BUDGET_S = 30 * 60  # stop early and still score the test split
BATCH = 128
IMG = 32
OUT = Path(os.environ.get("OUT_DIR", "/kaggle/working"))
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
dev = "cuda" if torch.cuda.is_available() else "cpu"
print("device", dev, "torch", torch.__version__, flush=True)

# ---------- data ----------
root = next(Path(os.environ.get("DATA_DIR", "/kaggle/input")).rglob("nhcd"))
samples = []
for img in root.rglob("*.jpg"):
    rel = img.relative_to(root).parts  # e.g. ('nhcd', 'vowels', '9', '046_02.jpg')
    if len(rel) >= 3:
        samples.append((str(img), f"{rel[-3]}/{rel[-2]}"))
labels = sorted({lab for _, lab in samples})
l2i = {lab: i for i, lab in enumerate(labels)}
print("images", len(samples), "classes", len(labels), flush=True)

# stratified 80/10/10 split (deterministic)
by_label = defaultdict(list)
for s in samples:
    by_label[s[1]].append(s)
train, val, test = [], [], []
for lab in sorted(by_label):
    items = sorted(by_label[lab])
    random.Random(SEED).shuffle(items)
    n = len(items)
    n_test = max(1, round(n * 0.10))
    n_val = max(1, round(n * 0.10))
    test += items[:n_test]
    val += items[n_test:n_test + n_val]
    train += items[n_test + n_val:]
print("split train/val/test", len(train), len(val), len(test), flush=True)

norm = transforms.Normalize((0.5,), (0.5,))
tf_train = transforms.Compose([
    transforms.Grayscale(1),
    transforms.RandomAffine(degrees=8, translate=(0.06, 0.06), scale=(0.9, 1.1), fill=255),
    transforms.Resize((IMG, IMG)),
    transforms.ToTensor(), norm,
])
tf_eval = transforms.Compose([
    transforms.Grayscale(1), transforms.Resize((IMG, IMG)), transforms.ToTensor(), norm,
])


class DS(Dataset):
    def __init__(self, items, tf):
        self.items, self.tf = items, tf

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        path, lab = self.items[i]
        return self.tf(Image.open(path).convert("L")), l2i[lab]


train_dl = DataLoader(DS(train, tf_train), batch_size=BATCH, shuffle=True, num_workers=0, pin_memory=True)
val_dl = DataLoader(DS(val, tf_eval), batch_size=256, num_workers=0)
test_dl = DataLoader(DS(test, tf_eval), batch_size=256, num_workers=0)


# ---------- model ----------
class Block(nn.Module):
    def __init__(self, cin, cout):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(cin, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
            nn.Conv2d(cout, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
        )

    def forward(self, x):
        return self.net(x)


class CharCNN(nn.Module):
    def __init__(self, n_classes):
        super().__init__()
        self.features = nn.Sequential(Block(1, 48), Block(48, 96), Block(96, 192))  # 32 -> 4
        self.head = nn.Sequential(
            nn.Flatten(), nn.Dropout(0.35), nn.Linear(192 * 4 * 4, 256), nn.ReLU(inplace=True),
            nn.Dropout(0.35), nn.Linear(256, n_classes),
        )

    def forward(self, x):
        return self.head(self.features(x))


model = CharCNN(len(labels)).to(dev)
n_params = sum(p.numel() for p in model.parameters())
print("parameters", n_params, flush=True)
opt = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=5e-4)
sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=3e-3, epochs=EPOCHS, steps_per_epoch=len(train_dl))
use_amp = dev == "cuda"
scaler = torch.amp.GradScaler("cuda", enabled=use_amp)


def evaluate(dl, return_preds=False):
    model.eval()
    ys, ps, loss_sum, n = [], [], 0.0, 0
    with torch.no_grad(), torch.autocast(device_type=dev, enabled=use_amp):
        for x, y in dl:
            x, y = x.to(dev), y.to(dev)
            logits = model(x).float()
            loss_sum += F.cross_entropy(logits, y, reduction="sum").item()
            n += y.numel()
            ps.append(logits.argmax(1).cpu())
            ys.append(y.cpu())
    y_true = torch.cat(ys).numpy()
    y_pred = torch.cat(ps).numpy()
    acc = float((y_true == y_pred).mean())
    if return_preds:
        return acc, loss_sum / n, y_true, y_pred
    return acc, loss_sum / n


best_acc, best_state, log = -1.0, None, []
t0 = time.time()
epochs_run = 0
for ep in range(1, EPOCHS + 1):
    if time.time() - t0 > TIME_BUDGET_S:
        print("time budget reached, stopping after", ep - 1, "epochs", flush=True)
        break
    epochs_run = ep
    model.train()
    total, correct, loss_sum = 0, 0, 0.0
    for x, y in train_dl:
        x, y = x.to(dev, non_blocking=True), y.to(dev, non_blocking=True)
        opt.zero_grad(set_to_none=True)
        with torch.autocast(device_type=dev, enabled=use_amp):
            logits = model(x)
            loss = F.cross_entropy(logits, y, label_smoothing=0.05)
        scaler.scale(loss).backward()
        scaler.step(opt)
        scaler.update()
        sched.step()
        loss_sum += loss.item() * y.size(0)
        correct += (logits.argmax(1) == y).sum().item()
        total += y.size(0)
    v_acc, v_loss = evaluate(val_dl)
    rec = {"epoch": ep, "train_loss": round(loss_sum / total, 4), "train_acc": round(correct / total, 4),
           "val_loss": round(v_loss, 4), "val_acc": round(v_acc, 4), "seconds": round(time.time() - t0, 1)}
    log.append(rec)
    print(json.dumps(rec), flush=True)
    print("progress", ep, "val_acc", round(v_acc, 4), flush=True)
    if v_acc > best_acc:
        best_acc = v_acc
        best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

# ---------- held-out test, scored once with the selected checkpoint ----------
model.load_state_dict(best_state)
t_acc, t_loss, y_true, y_pred = evaluate(test_dl, return_preds=True)
macro_f1 = float(f1_score(y_true, y_pred, average="macro"))
weighted_f1 = float(f1_score(y_true, y_pred, average="weighted"))
majority = Counter(l2i[lab] for _, lab in train).most_common(1)[0][0]
baseline_acc = float((y_true == majority).mean())

per_cat = defaultdict(lambda: [0, 0])
for t, p in zip(y_true, y_pred):
    cat = labels[t].split("/")[0]
    per_cat[cat][0] += int(t == p)
    per_cat[cat][1] += 1
per_category = {k: round(v[0] / v[1], 4) for k, v in per_cat.items()}

cm = confusion_matrix(y_true, y_pred, labels=list(range(len(labels))))
pairs = [(int(cm[i, j]), labels[i], labels[j])
         for i in range(len(labels)) for j in range(len(labels)) if i != j and cm[i, j] > 0]
top_conf = [{"count": c, "true": a, "predicted": b} for c, a, b in sorted(pairs, reverse=True)[:10]]

metrics = {
    "device": dev,
    "dataset": "ashokpant/devanagari-character-dataset (NHCD handwritten Devanagari)",
    "task": "isolated handwritten Devanagari character classification (HTR building block, not full-line HTR)",
    "images": len(samples),
    "classes": len(labels),
    "split": {"train": len(train), "val": len(val), "test": len(test)},
    "epochs_planned": EPOCHS,
    "epochs_run": epochs_run,
    "parameters": n_params,
    "best_val_acc": round(best_acc, 4),
    "test_acc": round(t_acc, 4),
    "test_loss": round(t_loss, 4),
    "test_macro_f1": round(macro_f1, 4),
    "test_weighted_f1": round(weighted_f1, 4),
    "majority_class_baseline_acc": round(baseline_acc, 4),
    "per_category_test_acc": per_category,
    "top_confusions": top_conf,
    "train_seconds": round(time.time() - t0, 1),
}
print(json.dumps(metrics, indent=1, ensure_ascii=False), flush=True)
OUT.mkdir(parents=True, exist_ok=True)
torch.save({"state_dict": best_state, "labels": labels, "img_size": IMG, "normalize": [0.5, 0.5]},
           OUT / "devanagari_char_cnn.pt")
(OUT / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
(OUT / "training_log.json").write_text(json.dumps(log, indent=2))
(OUT / "labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1))
print("saved outputs", flush=True)
