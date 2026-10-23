"""Read a handwritten answer-sheet page with a vision model (Groq, Qwen).

The model transcribes Hindi and English as written, keeps question labels (1, 1(a), 4(b)) at the start
of their line, and writes maths in plain text and figures as short bracketed descriptions.
Returns None when the model cannot be used, so the caller can fall back to the line reader.
"""
import base64
import hashlib
import os
import sys
import threading
import time
from collections import OrderedDict
from typing import List, Optional, Tuple

import cv2
import httpx
import numpy as np

ADAPTERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "packages", "model-adapters")
sys.path.insert(0, os.path.abspath(ADAPTERS))

VISION_MODEL = os.environ.get("VISION_MODEL", "qwen/qwen3.8-27b")
# The vision model has its own per-minute token limit (8,000 on this account), separate from the text model.
_VISION_TPM = int(os.environ.get("VISION_TPM_BUDGET", "7000"))
_PAGE_COST = 2600           # measured: about 2,000 prompt + 450 completion tokens per page
_recent: List[Tuple[float, int]] = []
_cache: "OrderedDict[str, str]" = OrderedDict()   # transcripts of pages already read in this session
_CACHE_MAX = 300
_lock = threading.Lock()

PROMPT = (
    "Transcribe this handwritten answer-sheet page exactly, line by line, in the order it is written.\n"
    "Rules:\n"
    "- Keep Hindi in Devanagari and English in English, exactly as written. Do not translate.\n"
    "- Start a line with the question label when an answer begins there, exactly as written: 1, 2, 4(a), 1(b).\n"
    "- Sub-part markers inside an answer such as (i), (ii), (iii) belong to the answer text. Do not make them labels.\n"
    "- Write mathematics in plain text, for example x^2 + 3x = 10, or sqrt(2), or pi r^2.\n"
    "- For a figure, graph, map or table, write one line: [figure: short description of what it shows].\n"
    "- Output only the transcription. No introduction, no commentary."
)


def _jpeg(gray: np.ndarray, width: int = 900) -> bytes:
    img = gray
    if img.shape[1] > width:
        img = cv2.resize(img, (width, int(img.shape[0] * width / img.shape[1])), interpolation=cv2.INTER_AREA)
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return enc.tobytes()


def _vision_pace() -> None:
    """Wait until the last minute's vision token use leaves room for one more page."""
    while True:
        now = time.time()
        with _lock:
            _recent[:] = [(t, n) for t, n in _recent if now - t < 60.0]
            used = sum(n for _, n in _recent)
            if used + _PAGE_COST <= _VISION_TPM or not _recent:
                return
            oldest = min(t for t, _ in _recent)
        time.sleep(min(max(60.0 - (now - oldest), 0.5), 15.0))


def _vision_note(data: dict) -> None:
    try:
        n = int((data.get("usage") or {}).get("total_tokens") or _PAGE_COST)
    except (AttributeError, TypeError, ValueError):
        n = _PAGE_COST
    with _lock:
        _recent.append((time.time(), n))


def transcribe_image(gray: np.ndarray) -> Optional[str]:
    """Transcribe one page image. Returns the text, or None if the model could not be used."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None
    jpg = _jpeg(gray)
    digest = hashlib.sha256(jpg).hexdigest()
    with _lock:
        if digest in _cache:
            _cache.move_to_end(digest)
            return _cache[digest]
    body = {
        "model": VISION_MODEL,
        "temperature": 0.0,
        "max_completion_tokens": 2000,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpg).decode()}},
        ]}],
    }
    for attempt in range(4):
        _vision_pace()
        try:
            with httpx.Client(timeout=90) as client:
                resp = client.post("https://api.groq.com/openai/v1/chat/completions",
                                   headers={"Authorization": f"Bearer {key}"}, json=body)
        except Exception as exc:
            print(f"[vision] page not read: {type(exc).__name__}", file=sys.stderr)
            return None
        if resp.status_code == 429 and attempt < 3:
            time.sleep(min(max(float(resp.headers.get("retry-after", "5") or 5), 2.0), 60.0))
            continue
        if resp.status_code != 200:
            print(f"[vision] page not read: HTTP {resp.status_code}", file=sys.stderr)
            return None
        try:
            data = resp.json()
            _vision_note(data)
            text = (data["choices"][0]["message"]["content"] or "").strip()
        except Exception:
            return None
        if not text:
            return None
        # drop a chatty first line if the model adds one anyway
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if lines and lines[0].lower().startswith(("here is", "transcription", "sure")):
            lines = lines[1:]
        result = "\n".join(lines)
        with _lock:
            _cache[digest] = result
            while len(_cache) > _CACHE_MAX:
                _cache.popitem(last=False)
        return result
    return None
