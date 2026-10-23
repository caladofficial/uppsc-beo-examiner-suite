"""CRNN + CTC line recogniser for handwritten-style Devanagari/English answer lines.

Input: grey line image, 40 x 320 (white background, dark ink), values scaled to [-1, 1].
Output: per-timestep class log-probs over the character set plus CTC blank (index 0).
"""
import json
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

LINE_H, LINE_W = 40, 320


class CRNN(nn.Module):
    def __init__(self, n_classes, hidden=128):
        super().__init__()

        def cbr(i, o):
            return [nn.Conv2d(i, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True)]

        self.cnn = nn.Sequential(
            *cbr(1, 16), nn.MaxPool2d((2, 2)),          # 20 x 160
            *cbr(16, 32), nn.MaxPool2d((2, 2)),         # 10 x 80
            *cbr(32, 64), *cbr(64, 64), nn.MaxPool2d((2, 1)),   # 5 x 80
            *cbr(64, 96), nn.MaxPool2d((2, 1)),         # 2 x 80
        )
        self.rnn = nn.LSTM(96 * 2, hidden, num_layers=2, bidirectional=True, batch_first=True, dropout=0.1)
        self.fc = nn.Linear(hidden * 2, n_classes + 1)

    def forward(self, x):  # x: (B, 1, H, W)
        f = self.cnn(x)                               # (B, C, 2, T)
        b, c, h, t = f.shape
        f = f.permute(0, 3, 1, 2).reshape(b, t, c * h)  # (B, T, C*H)
        out, _ = self.rnn(f)
        return self.fc(out)                           # (B, T, K+1)


def to_tensor(arr_uint8):
    x = torch.from_numpy(arr_uint8.astype(np.float32) / 127.5 - 1.0)
    return x[None, None]  # (1,1,H,W)


def greedy_decode(logits, charset):
    """logits: (T, K+1) numpy. Returns (text, mean confidence of kept characters)."""
    probs = np.exp(logits - logits.max(axis=-1, keepdims=True))
    probs /= probs.sum(axis=-1, keepdims=True)
    best = probs.argmax(axis=-1)
    chars, confs, prev = [], [], -1
    for t, k in enumerate(best):
        if k != prev and k != 0:
            chars.append(charset[k - 1])
            confs.append(float(probs[t, k]))
        prev = k
    conf = float(np.mean(confs)) if confs else 0.0
    return "".join(chars), conf


def load_checkpoint(path, device="cpu"):
    ck = torch.load(path, map_location=device, weights_only=False)
    model = CRNN(len(ck["charset"]), hidden=ck.get("hidden", 128))
    model.load_state_dict(ck["state_dict"])
    model.eval()
    return model, ck["charset"]


def edit_distance(a, b):
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]
