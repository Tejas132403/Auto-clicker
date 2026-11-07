#!/usr/bin/env python3
"""
King Auto Quiz Bot  -  com.shake.master "Daily Gaming Quiz"
===========================================================
Fully automatic:  read question -> answer with Gemini -> tap Add Bonus
-> watch ad -> close ad the instant its Close/Skip button appears
-> next question ... until all 25 are done.

Key features
------------
* Reads the UI hierarchy (uiautomator) instead of guessing coordinates.
* Answers using Gemini (fast flash model) with retries.
* Keeps a local answer cache (quiz_answers.json) -> "trained" over runs.
* Ad handling is event driven: it polls the ad activity every ~0.5 s and
  taps Close/Skip as soon as the button is really present.  No fixed 30 s
  waits, so ads are cut in ~1 s after they become closable.
* Recovers from ad landing pages / Play Store / browser (presses Back).
* Detailed log in bot_log.txt.

Usage
-----
    .venv2\\Scripts\\python.exe king_quiz_bot.py            # run until 25/25
    .venv2\\Scripts\\python.exe king_quiz_bot.py --dry-run   # decide only, no taps
    .venv2\\Scripts\\python.exe king_quiz_bot.py --max-steps 5
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "ai_config.json")
CACHE_FILE = os.path.join(BASE_DIR, "quiz_answers.json")
LOG_FILE = os.path.join(BASE_DIR, "bot_log.txt")
TMP_XML = "/sdcard/king_bot_ui.xml"

QUIZ_PKG = "com.shake.master"
ADS_MARKERS = ("gms.ads", "google.android.gms.ads", "adactivity")
CLOSE_WORDS = {"close", "close ad", "skip", "skip ad", "dismiss", "×", "✕", "x", "done"}
NEXT_WORDS = {"continue", "next", "ok", "okay", "claim", "collect", "add", "add bonus", "submit"}

ADB_CANDIDATES = [
    r"C:\Users\tejas\AppData\Local\Android\Sdk\platform-tools\adb.exe",
    r"D:\mirzapur\scrcpy-win64-v3.2\platform-tools\adb.exe",
    r"C:\Users\tejas\Desktop\platform-tools\adb.exe",
    "adb",
]


def find_adb():
    for p in ADB_CANDIDATES:
        if os.path.exists(p):
            return p
    return "adb"


ADB = find_adb()


# --------------------------------------------------------------------------- #
#  logging / adb
# --------------------------------------------------------------------------- #
def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def adb(args, binary=False, timeout=30):
    try:
        res = subprocess.run([ADB] + args, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=timeout)
        if binary:
            return res.stdout
        return (res.stdout + res.stderr).decode("utf-8", "replace").strip()
    except subprocess.TimeoutExpired:
        log(f"ADB timeout: {' '.join(args)}")
        return b"" if binary else ""
    except Exception as e:
        log(f"ADB error: {e}")
        return b"" if binary else ""


def tap(x, y):
    log(f"TAP ({x},{y})")
    adb(["shell", "input", "tap", str(int(x)), str(int(y))])


def press_back():
    log("BACK key")
    adb(["shell", "input", "keyevent", "4"])


def get_focus():
    out = adb(["shell", "dumpsys", "window"], timeout=15)
    m = re.search(r"mCurrentFocus=Window\{[^}]*?\s([\w\.]+)/([\w\.\$]+)", out)
    if m:
        return m.group(1), m.group(2)
    return "", ""


# --------------------------------------------------------------------------- #
#  UI hierarchy
# --------------------------------------------------------------------------- #
def parse_bounds(s):
    m = re.findall(r"\[(\d+),(\d+)\]", s or "")
    if len(m) == 2:
        x1, y1 = int(m[0][0]), int(m[0][1])
        x2, y2 = int(m[1][0]), int(m[1][1])
        return {"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "cx": (x1 + x2) // 2, "cy": (y1 + y2) // 2,
                "area": max(1, (x2 - x1) * (y2 - y1))}
    return None


class Node:
    __slots__ = ("text", "desc", "rid", "cls", "pkg", "bounds",
                 "clickable", "click")

    def __init__(self, el, click):
        self.text = (el.attrib.get("text") or "").strip()
        self.desc = (el.attrib.get("content-desc") or "").strip()
        self.rid = el.attrib.get("resource-id") or ""
        self.cls = el.attrib.get("class") or ""
        self.pkg = el.attrib.get("package") or ""
        self.bounds = parse_bounds(el.attrib.get("bounds"))
        self.clickable = el.attrib.get("clickable") == "true"
        self.click = click or (self.bounds["cx"], self.bounds["cy"]) if self.bounds else None

    @property
    def label(self):
        return self.text or self.desc


def dump_nodes():
    """Return list[Node] for the current screen, or [] on failure."""
    for _ in range(4):
        out = adb(["shell", "uiautomator", "dump", TMP_XML], timeout=25)
        if "dumped" in out.lower():
            break
        time.sleep(0.5)
    raw = adb(["exec-out", "cat", TMP_XML], binary=True, timeout=25)
    if not raw:
        return []
    txt = raw.decode("utf-8", "replace")
    start = txt.find("<hierarchy")
    end = txt.rfind("</hierarchy>")
    if start < 0:
        return []
    if end > 0:
        txt = txt[start:end + len("</hierarchy>")]
    else:
        txt = txt[start:]
    try:
        root = ET.fromstring(txt)
    except Exception as e:
        log(f"XML parse error: {e}")
        return []

    parent_of = {}
    for p in root.iter():
        for c in p:
            parent_of[c] = p

    nodes = []
    for el in root.iter("node"):
        b = parse_bounds(el.attrib.get("bounds"))
        if not b:
            continue
        # smallest clickable ancestor = best tap target
        best = b if el.attrib.get("clickable") == "true" else None
        p = parent_of.get(el)
        while p is not None and p.tag == "node":
            if p.attrib.get("clickable") == "true":
                pb = parse_bounds(p.attrib.get("bounds"))
                if pb and (best is None or pb["area"] < best["area"]):
                    best = pb
            p = parent_of.get(p)
        if best is None:
            best = b
        nodes.append(Node(el, (best["cx"], best["cy"])))
    return nodes


# --------------------------------------------------------------------------- #
#  screen state helpers
# --------------------------------------------------------------------------- #
def by_rid(nodes, suffix):
    for n in nodes:
        if n.rid and n.rid.endswith(suffix):
            return n
    return None


def by_text(nodes, wanted):
    wanted = wanted.lower()
    for n in nodes:
        if n.label.lower() == wanted:
            return n
    return None


def find_close(nodes):
    for n in nodes:
        t = n.label.lower().strip()
        if not t:
            continue
        if t in CLOSE_WORDS or re.fullmatch(r"(close|skip)(\s+ad)?(\s*[\(\[].*)?", t):
            return n
        if t.startswith("close") and len(t) < 30:
            return n
        if t.startswith("skip") and len(t) < 30:
            return n
    return None


def find_button(nodes, words):
    for n in nodes:
        t = n.label.lower().strip()
        if t in words:
            return n
    return None


def extract_quiz(nodes):
    q = by_rid(nodes, "tvQuestion")
    if not q or not q.text:
        return None
    question = q.text.strip()

    labels = [n for n in nodes if n.rid and n.rid.endswith("tvOptionLabel")]
    texts = [n for n in nodes if n.rid and n.rid.endswith("tvOptionText")]
    options = []
    for t in texts:
        if not t.bounds or not t.text:
            continue
        best_lbl = None
        for l in labels:
            if l.bounds and abs(l.bounds["cy"] - t.bounds["cy"]) < 90:
                best_lbl = l
                break
        letter = (best_lbl.text if best_lbl else "?").strip().rstrip(".")
        options.append({
            "letter": letter.upper(),
            "text": t.text.strip(),
            "tap": t.click,
            "cy": t.bounds["cy"],
        })
    options.sort(key=lambda o: o["cy"])
    if len(options) < 2:
        return None
    return {"question": question, "options": options}


def get_progress(nodes):
    c = by_rid(nodes, "progress_count")
    if c and c.text:
        return c.text.replace(" ", "")
    return ""


# --------------------------------------------------------------------------- #
#  Gemini answering + cache
# --------------------------------------------------------------------------- #
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"cache save failed: {e}")


def qhash(question, options):
    raw = question + "||" + "|".join(o["text"] for o in options)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def gemini_call(prompt, cfg, model):
    key = cfg.get("gemini_api_key", "")
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 120},
    }
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def ask_gemini(question, options, cfg):
    opt_lines = "\n".join(f"{o['letter']}. {o['text']}" for o in options)
    prompt = (
        "You are an expert on the mobile game Free Fire and general gaming. "
        "Answer this multiple-choice quiz (it may be in Hindi, Hinglish or English).\n"
        "Choose the single most correct option.\n"
        "Reply with STRICT JSON only, no markdown:\n"
        '{"answer":"A","confidence":0.95}\n\n'
        f"Question: {question}\n{opt_lines}\n"
    )
    models = []
    for m in (cfg.get("quiz_model"), cfg.get("gemini_model"),
              "gemini-3-flash-preview", "gemini-3.1-pro-preview",
              "gemini-2.5-pro", "gemini-2.5-flash"):
        if m and m not in models:
            models.append(m)

    for model in models:
        for attempt in range(2):
            try:
                raw = gemini_call(prompt, cfg, model)
                m = re.search(r"\{.*?\}", raw, re.S)
                if m:
                    j = json.loads(m.group(0))
                    ans = str(j.get("answer", "")).strip().upper()[:1]
                    conf = float(j.get("confidence", 0.7))
                    if ans in {o["letter"] for o in options}:
                        log(f"GEMINI[{model}] -> {ans} (conf {conf:.2f})")
                        return ans, conf
                m2 = re.search(r"\b([A-D])\b", raw.upper())
                if m2 and m2.group(1) in {o["letter"] for o in options}:
                    log(f"GEMINI[{model}] raw -> {m2.group(1)}")
                    return m2.group(1), 0.5
            except urllib.error.HTTPError as e:
                log(f"GEMINI[{model}] HTTP {e.code} (attempt {attempt+1})")
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break
            except Exception as e:
                log(f"GEMINI[{model}] error: {e}")
                break
    return None, 0.0


def local_guess(question, options):
    """Cheap keyword fallback for the most common Free Fire questions."""
    q = question.lower()
    rules = [
        (("खरीद", "buy", "purchase"), ("diamond", "डायमंड")),
        (("कपड़े", "clothes", "outfit", "dress"), ("outfit", "character")),
        (("संदेश", "message", "team"), ("quick message", "message")),
        (("हेल्थ", "health", "hp"), ("health",)),
        (("गोली", "bullet", "ammo"), ("ammo", "bullet")),
        (("गाड़ी", "vehicle", "car"), ("vehicle",)),
        (("मैप", "map"), ("map",)),
    ]
    for qkeys, akeys in rules:
        if any(k in q for k in qkeys):
            for o in options:
                if any(a in o["text"].lower() for a in akeys):
                    return o["letter"], 0.4
    return None, 0.0


def decide_answer(question, options, cfg, cache):
    key = qhash(question, options)
    if key in cache:
        saved = str(cache[key].get("answer", "")).upper()[:1]
        if saved in {o["letter"] for o in options}:
            log(f"CACHE hit -> {saved}")
            return saved, 1.0, key
    ans, conf = ask_gemini(question, options, cfg)
    if not ans:
        log("Gemini failed, trying local heuristic")
        ans, conf = local_guess(question, options)
    if not ans:
        ans = options[0]["letter"]
        conf = 0.1
        log(f"FALLBACK first option -> {ans}")
    return ans, conf, key


# --------------------------------------------------------------------------- #
#  actions
# --------------------------------------------------------------------------- #
def answer_question(nodes, cfg, cache, dry=False):
    quiz = extract_quiz(nodes)
    if not quiz:
        return False
    log(f"QUESTION: {quiz['question']}")
    for o in quiz["options"]:
        log(f"   {o['letter']}. {o['text']}")
    ans, conf, key = decide_answer(quiz["question"], quiz["options"], cfg, cache)
    chosen = next((o for o in quiz["options"] if o["letter"] == ans), None)
    if not chosen:
        chosen = quiz["options"][0]
    log(f"ANSWER -> {chosen['letter']}. {chosen['text']} ({conf:.2f})")
    if dry:
        return True
    tx, ty = chosen["tap"]
    tap(tx, ty)
    cache[key] = {
        "question": quiz["question"],
        "options": {o["letter"]: o["text"] for o in quiz["options"]},
        "answer": chosen["letter"],
        "confidence": conf,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_json(CACHE_FILE, cache)
    return True


def close_ad(nodes, focus_pkg, cfg):
    """Close an ad if possible. Returns True if something was tapped."""
    # 1) a real Close / Skip button in the hierarchy
    btn = find_close(nodes)
    if btn and btn.click:
        log(f"AD CLOSE button '{btn.label}' at {btn.click}")
        tap(*btn.click)
        return True
    # 2) landed on Play Store / browser by accident -> go back
    if focus_pkg and focus_pkg not in (QUIZ_PKG, "com.google.android.gms"):
        log(f"AD landed on foreign app {focus_pkg} -> BACK")
        press_back()
        time.sleep(0.6)
        press_back()
        return True
    return False


def run(max_steps=400, dry=False, poll=0.6):
    cfg = load_json(CONFIG_FILE, {})
    cache = load_json(CACHE_FILE, {})

    log("=" * 60)
    log("KING QUIZ BOT started")
    focus_pkg, focus_act = get_focus()
    log(f"focus: {focus_pkg}/{focus_act}")
    if QUIZ_PKG not in focus_pkg:
        log(f"WARNING: {QUIZ_PKG} is not in the foreground. Open the quiz app first.")

    last_state = None
    idle = 0
    for step in range(1, max_steps + 1):
        focus_pkg, focus_act = get_focus()
        nodes = dump_nodes()
        if not nodes and not focus_pkg:
            time.sleep(1)
            continue

        progress = get_progress(nodes)
        in_ad_activity = any(m in (focus_pkg + focus_act).lower() for m in ADS_MARKERS)
        close_btn = find_close(nodes)
        bonus_btn = by_text(nodes, "Add Bonus") or by_text(nodes, "Add")
        quiz = extract_quiz(nodes)
        loading = any("ad is loading" in n.label.lower() for n in nodes if n.label)
        complete = any(k in (n.label.lower()) for n in nodes
                       for k in ("completed", "congratulations", "all questions", "claim reward"))

        # ---- report state changes only
        state = ("AD" if (in_ad_activity or close_btn) else
                 "QUIZ" if quiz else
                 "BONUS" if bonus_btn else
                 "LOADING" if loading else
                 "COMPLETE" if complete else "IDLE")
        if state != last_state:
            log(f"STATE -> {state}  progress={progress or '-'}")
            last_state = state

        # ---- act in priority order
        if in_ad_activity or close_btn or loading:
            if close_btn:
                close_ad(nodes, focus_pkg, cfg)
                time.sleep(0.8)
            else:
                # ad still playing / loading - wait for the close button
                time.sleep(poll)
            idle = 0
            continue

        if quiz:
            answer_question(nodes, cfg, cache, dry=dry)
            time.sleep(1.2)
            idle = 0
            continue

        if bonus_btn:
            log(f"BONUS button '{bonus_btn.label}' at {bonus_btn.click}")
            if not dry:
                tap(*bonus_btn.click)
            time.sleep(1.5)
            idle = 0
            continue

        if complete:
            btn = find_button(nodes, NEXT_WORDS)
            log(f"COMPLETION screen detected. button={btn.label if btn else None}")
            if btn and not dry:
                tap(*btn.click)
                time.sleep(1.5)
            log("All tasks finished.")
            break

        # unknown screen: try a generic next/continue/claim button, else wait
        btn = find_button(nodes, NEXT_WORDS - {"add bonus", "add"})
        if btn and not dry:
            log(f"generic button '{btn.label}' -> tap")
            tap(*btn.click)
            time.sleep(1.2)
            idle = 0
            continue

        idle += 1
        if idle % 10 == 0:
            log("Waiting... (no actionable element). If stuck, check the phone.")
        time.sleep(1.0)

    log("BOT stopped.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-steps", type=int, default=400)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--poll", type=float, default=0.6)
    args = ap.parse_args()
    try:
        run(max_steps=args.max_steps, dry=args.dry_run, poll=args.poll)
    except KeyboardInterrupt:
        log("Interrupted by user.")
