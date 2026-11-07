"""Quick helper: capture phone screen and ask Gemini vision what is on it."""
import base64
import json
import os
import subprocess
import sys
import urllib.request

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_config.json")
SHOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vision_shot.png")


def load_config():
    with open(CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)


def capture():
    with open(SHOT, "wb") as f:
        subprocess.run(["adb", "exec-out", "screencap", "-p"], stdout=f, check=True)
    return SHOT


def ask(img_path, prompt, cfg):
    key = cfg.get("gemini_api_key", "")
    model = cfg.get("gemini_vision_model") or cfg.get("gemini_model") or "gemini-2.5-flash"
    if model not in ("gemini-2.5-flash", "gemini-2.5-pro", "gemini-3-flash-preview",
                     "gemini-3.1-pro-preview", "gemini-flash-latest", "gemini-flash-lite-latest",
                     "gemini-2.5-flash-lite"):
        model = "gemini-2.5-flash"
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": b64}},
            ]
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode())
    return data["candidates"][0]["content"]["parts"][0]["text"]


if __name__ == "__main__":
    cfg = load_config()
    prompt = sys.argv[1] if len(sys.argv) > 1 else (
        "You are looking at an Android phone screenshot (1080x2400). "
        "Describe exactly what is shown. If there is an advertisement, say so and "
        "identify any close (X), skip, or continue button with its pixel x,y center. "
        "Reply in JSON: {\"screen\":\"...\",\"ad\":true/false,\"tap\":[x,y] or null,\"notes\":\"...\"}"
    )
    path = capture()
    print(ask(path, prompt, cfg))
