"""Test a vision model as the sheet reader: transcribe one page, compare with ground-truth lines."""
import os, sys, json, base64, time, difflib, httpx, fitz, cv2, numpy as np

KEY = os.environ["GROQ_API_KEY"]
MODEL = os.environ.get("VISION_MODEL", "qwen/qwen3.8-27b")
PROMPT = ("Transcribe this handwritten answer-sheet page exactly, line by line, in the order written. "
          "Keep Hindi (Devanagari) in Devanagari and English in English. Keep question numbers and sub-part labels "
          "such as 1(a), (i), (ii), 2., 3. exactly as written. For maths, write the formula in plain text. "
          "For a figure or graph write [figure: short description]. Output only the transcription, no commentary.")

def page_b64(pdf, idx, width=1100):
    doc = fitz.open(pdf)
    pix = doc[idx].get_pixmap(dpi=150, colorspace=fitz.csGRAY)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
    if pix.w > width:
        img = cv2.resize(img, (width, int(pix.h * width / pix.w)), interpolation=cv2.INTER_AREA)
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(enc.tobytes()).decode(), len(enc.tobytes())

def transcribe(b64):
    body = {"model": MODEL, "temperature": 0.0, "max_completion_tokens": 1800,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}]}]}
    for attempt in range(4):
        r = httpx.post("https://api.groq.com/openai/v1/chat/completions",
                       headers={"Authorization": "Bearer " + KEY}, json=body, timeout=120)
        if r.status_code == 429:
            time.sleep(min(float(r.headers.get("retry-after", "10")), 30)); continue
        if r.status_code != 200:
            return None, f"HTTP {r.status_code} {r.text[:200]}"
        return r.json()["choices"][0]["message"]["content"], r.json().get("usage")
    return None, "rate limited"

if __name__ == "__main__":
    pdf, idx = sys.argv[1], int(sys.argv[2])
    b64, size = page_b64(pdf, idx)
    t0 = time.time()
    text, usage = transcribe(b64)
    print("bytes", size, "seconds", round(time.time() - t0, 1), "usage", usage)
    print(text)
