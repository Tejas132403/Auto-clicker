#!/usr/bin/env python3
"""
King Auto Quiz Bot  -  com.shake.master "Daily Gaming Quiz"
===========================================================
Fully automatic:  read question -> answer with Gemini -> tap Add Bonus
-> watch ad -> close the ad the instant its Close/Skip button appears
-> next question ... until all 25 are done.

v2 improvements
---------------
* One-round-trip UI dump (dump + cat in a single adb call) -> ~2x faster.
* Dedicated ad loop: polls every ~0.25 s, taps Close/Skip/end-card buttons
  immediately, handles "exit ad?" dialogs, and recovers from Play Store /
  browser landings without losing the quiz.
* Hard-coded safe fallbacks for Mintegral / AdMob / Unity / AppLovin layouts.
* Cache is keyed by question text (survives option shuffling) and stores the
  answer TEXT, not only the letter.
* Learns from the app's Correct/Wrong feedback and blacklists wrong options.
* Bot-check detection -> pauses and saves a screenshot instead of tapping.
* Detailed log in bot_log.txt.

Usage
-----
    .venv2\\Scripts\\python.exe king_quiz_bot.py                # run until 25/25
    .venv2\\Scripts\\python.exe king_quiz_bot.py --dry-run      # decide only, no taps
    .venv2\\Scripts\\python.exe king_quiz_bot.py --max-steps 50
    .venv2\\Scripts\\python.exe king_quiz_bot.py --serial emulator-5554
    .venv2\\Scripts\\python.exe king_quiz_bot.py --open         # bring app to front
"""

import argparse
import difflib
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

# --------------------------------------------------------------------------- #
#  tunables
# --------------------------------------------------------------------------- #
DEFAULT_POLL = 0.25          # idle / ad poll interval
ACTION_SETTLE = 0.30         # wait after a tap before the next dump
AD_MAX_SECONDS = 150         # hard safety limit for one ad
SAME_QUESTION_RETRY = 6.0    # re-tap the same question after this many seconds

CLOSE_WORDS = {
    "close", "close ad", "close ads", "skip", "skip ad", "skip ads",
    "dismiss", "×", "✕", "✖", "╳", "x", "done", "no thanks", "no, thanks",
    "not now", "got it", "ok", "okay", "continue", "exit", "exit ad",
    "leave", "close app", "end ad", "proceed",
}
NEXT_WORDS = {
    "continue", "next", "ok", "okay", "claim", "collect", "submit", "done",
    "got it", "claim reward", "collect reward", "play again", "start",
}
BONUS_WORDS = {
    "add bonus", "add bonus +", "watch ad", "watch video", "watch ads",
    "get bonus", "claim bonus", "bonus", "extra bonus", "double reward",
}
COMPLETE_WORDS = {
    "completed", "congratulations", "all questions", "all tasks",
    "claim reward", "come back tomorrow", "quiz completed",
}

AD_RID_MARKERS = (
    "app-interstitial-slot", "mys-creative", "mys-wrapper", "gmsg-video-player",
    "adactivity", "ad-container", "ad_container", "adview", "interstitial",
    "rewarded", "abgcp", "abgc", "ad_badge", "adbadge", "skip_button",
    "close_button", "ad_choice", "adchoices", "video-player",
)
AD_TEXT_MARKERS = (
    "ad is loading", "skip ad", "close ad", "advertisement", "sponsored",
    "rewarded ad", "watch ad to", "ad will end", "ad ends in",
    "you will be rewarded", "advertisement.",
)

FEEDBACK_CORRECT = (
    "correct answer", "correct!", "correct ", "right answer", "well done",
    "सही", "बधाई", "शाबाश", "great job",
)
FEEDBACK_WRONG = (
    "wrong answer", "incorrect", "oops", "गलत", "better luck", "try again",
    "सही उत्तर", "उत्तर गलत",
)
BOT_CHECK_WORDS = (
    "verify you are human", "verify that you are human", "captcha",
    "not a robot", "i'm not a robot", "bot check", "suspicious activity",
    "security check", "human verification",
)

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
SERIAL = ""
SCREEN_W = 1080
SCREEN_H = 2400


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
    cmd = [ADB]
    if SERIAL:
        cmd += ["-s", SERIAL]
    cmd += args
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE,
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
    log(f"TAP ({int(x)},{int(y)})")
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


def get_screen_size():
    out = adb(["shell", "wm", "size"], timeout=10)
    m = re.search(r"(\d+)x(\d+)", out)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 1080, 2400


def setup_device(serial=None):
    """Pick a device and make sure it is online."""
    global SERIAL, SCREEN_W, SCREEN_H
    env_serial = os.environ.get("ADB_SERIAL", "").strip()
    SERIAL = serial or env_serial
    out = adb(["devices"], timeout=10)
    if not SERIAL:
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                SERIAL = parts[0]
                break
    if not SERIAL:
        log("No ADB device found. Connect the phone with USB debugging ON.")
        return False
    # confirm it is really usable
    state = adb(["get-state"], timeout=10)
    if "device" not in state:
        log(f"Device {SERIAL} is not ready (state={state!r}).")
        return False
    model = adb(["shell", "getprop", "ro.product.model"], timeout=10)
    SCREEN_W, SCREEN_H = get_screen_size()
    log(f"Device: {SERIAL} ({model or 'unknown'})  screen={SCREEN_W}x{SCREEN_H}")
    return True


def bring_app_foreground():
    log(f"Bringing {QUIZ_PKG} to the foreground")
    out = adb(["shell", "cmd", "package", "resolve-activity", "--brief", QUIZ_PKG],
              timeout=10)
    m = re.search(r"([\w\.]+/[\w\.\$]+)", out)
    if m:
        adb(["shell", "am", "start", "-n", m.group(1)], timeout=15)
    else:
        adb(["shell", "monkey", "-p", QUIZ_PKG, "-c",
             "android.intent.category.LAUNCHER", "1"], timeout=15)


def screenshot(path):
    raw = adb(["exec-out", "screencap", "-p"], binary=True, timeout=20)
    if raw:
        try:
            with open(path, "wb") as f:
                f.write(raw)
            log(f"Screenshot saved: {path}")
            return True
        except Exception as e:
            log(f"Screenshot failed: {e}")
    return False


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
        if click:
            self.click = click
        elif self.bounds:
            self.click = (self.bounds["cx"], self.bounds["cy"])
        else:
            self.click = None

    @property
    def label(self):
        return self.text or self.desc


def _read_hierarchy():
    """Dump + fetch in ONE adb round-trip. Falls back to the slow way."""
    cmd = (f"rm -f {TMP_XML}; uiautomator dump --compressed {TMP_XML} "
           f">/dev/null 2>&1; cat {TMP_XML} 2>/dev/null")
    out = adb(["shell", cmd], timeout=15)
    if "<hierarchy" in out:
        return out
    # fallback for older / picky devices
    adb(["shell", "uiautomator", "dump", "--compressed", TMP_XML], timeout=25)
    raw = adb(["exec-out", "cat", TMP_XML], binary=True, timeout=20)
    return raw.decode("utf-8", "replace") if raw else ""


def dump_nodes():
    """Return list[Node] for the current screen, or [] on failure."""
    txt = ""
    for attempt in range(3):
        try:
            txt = _read_hierarchy()
        except Exception as e:
            log(f"dump error: {e}")
            txt = ""
        if "<hierarchy" in txt:
            break
        time.sleep(0.15)

    start = txt.find("<hierarchy")
    if start < 0:
        return []
    end = txt.rfind("</hierarchy>")
    if end > 0:
        txt = txt[start:end + len("</hierarchy>")]
    else:
        txt = txt[start:]
    try:
        root = ET.fromstring(txt)
    except Exception:
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
    wanted = wanted.lower().strip()
    for n in nodes:
        if n.label.lower().strip() == wanted:
            return n
    return None


def all_labels(nodes, max_len=60):
    out = []
    for n in nodes:
        lab = n.label.lower().strip()
        if lab and len(lab) <= max_len:
            out.append(lab)
    return " | ".join(out)


def find_close(nodes):
    """A real Close / Skip / X / end-card button, or None."""
    # 1) text / content-desc
    for n in nodes:
        t = n.label.lower().strip()
        if not t:
            continue
        if t in CLOSE_WORDS:
            return n
        if re.fullmatch(r"(close|skip|dismiss)(\s+(ad|ads))?(\s*[\(\[].*)?", t):
            return n
        if re.fullmatch(r"(close|skip|dismiss)\s*(in|after)?\s*\d+\s*s?", t):
            return n
        if re.fullmatch(r"[×✕✖╳x]", t):
            return n
        if t.startswith("close") and len(t) < 40:
            return n
        if t.startswith("skip") and len(t) < 40:
            return n
    # 2) resource-id says close/skip
    for n in nodes:
        r = (n.rid or "").lower()
        if any(k in r for k in ("btnclose", "btn_close", "close_btn",
                                "skip_button", "btnskip", "btn_skip",
                                "dismiss", "ivclose", "iv_close")):
            if n.click:
                return n
    # 3) unlabeled clickable X in the top-right corner (common ad UI)
    best = None
    for n in nodes:
        if not n.click or not n.bounds or n.label:
            continue
        b = n.bounds
        if (b["x1"] >= SCREEN_W * 0.70 and b["y2"] <= SCREEN_H * 0.16
                and b["area"] <= SCREEN_W * SCREEN_H * 0.10):
            if best is None or b["area"] < best.bounds["area"]:
                best = n
    return best


def find_button(nodes, words):
    for n in nodes:
        t = n.label.lower().strip()
        if t in words:
            return n
    return None


def find_contains(nodes, words):
    for n in nodes:
        t = n.label.lower().strip()
        if any(w in t for w in words):
            return n
    return None


def find_bonus(nodes):
    for n in nodes:
        t = n.label.lower().strip()
        if t in BONUS_WORDS:
            return n
        if "add bonus" in t or "watch ad" in t or "watch video" in t:
            if len(t) < 40:
                return n
    for n in nodes:
        r = (n.rid or "").lower()
        if "bonus" in r and n.click:
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
    return {
        "question": question,
        "options": options,
        "sig": qhash(question, options),
    }


def get_progress(nodes):
    rem = by_rid(nodes, "progress_remaining_count")
    tot = by_rid(nodes, "progress_count")
    parts = []
    if rem and rem.text:
        parts.append(rem.text.strip())
    if tot and tot.text:
        parts.append(tot.text.strip())
    return "".join(parts).replace(" ", "")


def looks_like_ad(nodes, focus_pkg="", focus_act=""):
    blob = f"{focus_pkg}/{focus_act}".lower()
    if any(m in blob for m in ("gms.ads", "adactivity", "ads.adactivity")):
        return True
    for n in nodes:
        r = (n.rid or "").lower()
        if any(m in r for m in AD_RID_MARKERS):
            return True
        p = (n.pkg or "").lower()
        if "gms.ads" in p:
            return True
        lab = n.label.lower()
        if lab and any(m in lab for m in AD_TEXT_MARKERS):
            return True
    return False


SYSTEM_PKGS = {
    "android", "com.android.systemui", "com.android.settings",
    "com.google.android.gms", "com.google.android.gsf",
    "com.android.launcher", "com.android.launcher3",
    "com.google.android.apps.nexuslauncher", "com.miui.home",
    "com.sec.android.app.launcher", "com.oppo.launcher", "com.vivo.launcher",
    "com.transsion.XOSLauncher", "com.google.android.inputmethod.latin",
}


def foreign_pkg(nodes):
    """Return a package that is neither the quiz app nor a system UI."""
    for n in nodes:
        p = (n.pkg or "").strip()
        if not p:
            continue
        if p == QUIZ_PKG or p.startswith(QUIZ_PKG + ":"):
            continue
        if p in SYSTEM_PKGS:
            continue
        if p.startswith("com.google.android.gms") or p.startswith("com.android"):
            continue
        return p
    return ""


def is_complete(nodes, progress):
    labels = all_labels(nodes, 80)
    if any(w in labels for w in COMPLETE_WORDS):
        return True
    m = re.match(r"(\d+)/(\d+)", (progress or "").replace(" ", ""))
    if m and int(m.group(1)) >= int(m.group(2)) > 0:
        return True
    return False


def is_bot_check(nodes):
    labels = all_labels(nodes, 120)
    return any(w in labels for w in BOT_CHECK_WORDS)


# --------------------------------------------------------------------------- #
#  Gemini answering + trained cache
# --------------------------------------------------------------------------- #
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        log(f"cache save failed: {e}")


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"[^\w\u0900-\u097F]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def qhash(question, options):
    raw = question + "||" + "|".join(o["text"] for o in options)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def qkey(question):
    """Hash of the question text only -> survives option shuffling."""
    return "q" + hashlib.sha1(norm(question).encode("utf-8")).hexdigest()[:15]


def normalize_cache(cache):
    """Re-key every entry by question text and keep the best copy."""
    out = {}
    for k, e in (cache or {}).items():
        if not isinstance(e, dict) or not e.get("question"):
            continue
        nk = qkey(e["question"])
        old = out.get(nk)
        if old is None or float(e.get("confidence") or 0) >= float(old.get("confidence") or 0):
            out[nk] = e
    return out


def cache_lookup(cache, question, options):
    """Return (letter, entry, score). Matches by answer TEXT, not letter."""
    qn = norm(question)
    best, best_score = None, 0.0
    for e in cache.values():
        if not isinstance(e, dict):
            continue
        eq = norm(e.get("question", ""))
        if not eq:
            continue
        if eq == qn:
            best, best_score = e, 1.0
            break
        score = difflib.SequenceMatcher(None, qn, eq).ratio()
        if score > best_score:
            best, best_score = e, score
    if not best or best_score < 0.90:
        return None, None, 0.0

    # 1) match stored answer text against current options
    at = norm(best.get("answer_text", ""))
    if at:
        for o in options:
            if norm(o["text"]) == at:
                return o["letter"], best, best_score
        cand = max(options, key=lambda o: difflib.SequenceMatcher(
            None, at, norm(o["text"])).ratio())
        if difflib.SequenceMatcher(None, at, norm(cand["text"])).ratio() >= 0.86:
            return cand["letter"], best, best_score

    # 2) old entries: map the saved letter's option text
    letter = str(best.get("answer", "")).upper()[:1]
    saved_text = norm((best.get("options") or {}).get(letter, ""))
    if saved_text:
        for o in options:
            if norm(o["text"]) == saved_text:
                return o["letter"], best, best_score
    return None, None, best_score


def gemini_call(prompt, cfg, model, temperature=0.0, max_tokens=120):
    key = cfg.get("gemini_api_key", "")
    if not key:
        raise RuntimeError("gemini_api_key missing in ai_config.json")
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature,
                             "maxOutputTokens": max_tokens},
    }
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={key}")
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def build_prompt(question, options):
    opt_lines = "\n".join(f"{o['letter']}. {o['text']}" for o in options)
    return (
        "You are an expert on the mobile game Free Fire, its daily quiz and "
        "general gaming trivia. The question may be in Hindi, Hinglish or English.\n"
        "Choose the single most correct option. Think carefully but answer fast.\n"
        "Reply with STRICT JSON only, no markdown:\n"
        '{"answer":"A","confidence":0.95}\n\n'
        f"Question: {question}\n{opt_lines}\n"
    )


def parse_answer(raw, options):
    valid = {o["letter"] for o in options}
    m = re.search(r"\{.*?\}", raw, re.S)
    if m:
        try:
            j = json.loads(m.group(0))
            ans = str(j.get("answer", "")).strip().upper()[:1]
            conf = float(j.get("confidence", 0.7))
            if ans in valid:
                return ans, conf
        except Exception:
            pass
    m2 = re.search(r"\b([A-D])\b", raw.upper())
    if m2 and m2.group(1) in valid:
        return m2.group(1), 0.5
    return None, 0.0


def model_list(cfg):
    models = []
    for m in (cfg.get("quiz_model"), cfg.get("gemini_model"),
              "gemini-3-flash-preview", "gemini-2.5-flash",
              "gemini-2.5-pro"):
        if m and m not in models:
            models.append(m)
    return models


def ask_gemini(question, options, cfg):
    prompt = build_prompt(question, options)
    for model in model_list(cfg):
        for attempt in range(2):
            try:
                raw = gemini_call(prompt, cfg, model)
                ans, conf = parse_answer(raw, options)
                if ans:
                    log(f"GEMINI[{model}] -> {ans} (conf {conf:.2f})")
                    return ans, conf
            except urllib.error.HTTPError as e:
                log(f"GEMINI[{model}] HTTP {e.code} (attempt {attempt + 1})")
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(1.0 * (attempt + 1))
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
        (("खरीद", "buy", "purchase", "diamond"), ("diamond", "डायमंड")),
        (("कपड़े", "clothes", "outfit", "dress"), ("outfit", "character")),
        (("संदेश", "message", "quick"), ("message", "quick message")),
        (("हेल्थ", "health", "hp"), ("health", "medkit")),
        (("गोली", "bullet", "ammo"), ("ammo", "bullet")),
        (("गाड़ी", "vehicle", "car", "jeep"), ("vehicle", "jeep")),
        (("मैप", "map"), ("bermuda", "purgatory", "kalahari", "alpine", "map")),
        (("पैराशूट", "parachute"), ("parachute",)),
        (("ग्लू", "gloo"), ("gloo",)),
        (("हेडशॉट", "headshot"), ("headshot", "head")),
    ]
    for qkeys, akeys in rules:
        if any(k in q for k in qkeys):
            for o in options:
                if any(a in o["text"].lower() for a in akeys):
                    return o["letter"], 0.4
    return None, 0.0


def decide_answer(question, options, cfg, cache, entry=None):
    letter, hit, score = cache_lookup(cache, question, options)
    if letter:
        wrong = [str(w).upper() for w in (hit.get("wrong") or [])]
        if letter not in wrong:
            log(f"CACHE hit ({score:.2f}) -> {letter}")
            return letter, max(0.9, float(hit.get("confidence") or 0.9)), hit
        log(f"CACHE hit but {letter} is blacklisted, asking Gemini")

    ans, conf = ask_gemini(question, options, cfg)
    if not ans:
        log("Gemini failed, trying local heuristic")
        ans, conf = local_guess(question, options)
    if not ans:
        wrong = [str(w).upper() for w in ((entry or {}).get("wrong") or [])]
        pool = [o for o in options if o["letter"] not in wrong] or options
        ans, conf = pool[0]["letter"], 0.1
        log(f"FALLBACK first option -> {ans}")
    return ans, conf, None


def record_answer(cache, quiz, chosen, conf, model_note=""):
    key = qkey(quiz["question"])
    entry = cache.get(key) or {}
    entry.update({
        "question": quiz["question"],
        "options": {o["letter"]: o["text"] for o in quiz["options"]},
        "answer": chosen["letter"],
        "answer_text": chosen["text"],
        "confidence": conf,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    if model_note:
        entry["model"] = model_note
    cache[key] = entry
    save_json(CACHE_FILE, cache)
    return entry


def learn_feedback(nodes, pending, cache):
    """Mark an answer correct/wrong using the app's own feedback text."""
    if not pending or time.time() - pending["at"] > 6:
        return
    blob = all_labels(nodes, 60)
    wrong = any(w in blob for w in FEEDBACK_WRONG)
    right = (not wrong) and any(w in blob for w in FEEDBACK_CORRECT)
    if not (wrong or right):
        return
    key = pending["key"]
    entry = cache.get(key)
    if not isinstance(entry, dict):
        return
    if wrong:
        w = entry.setdefault("wrong", [])
        if pending["letter"] not in w:
            w.append(pending["letter"])
        # do not trust this saved answer again
        entry.pop("answer", None)
        entry.pop("answer_text", None)
        entry["confidence"] = 0.0
        entry["last_wrong"] = pending["letter"]
        log(f"LEARN: '{pending['letter']}' marked WRONG and blacklisted")
    else:
        entry["correct"] = True
        entry["confidence"] = 1.0
        log(f"LEARN: '{pending['letter']}' confirmed CORRECT")
    save_json(CACHE_FILE, cache)


# --------------------------------------------------------------------------- #
#  ad handling
# --------------------------------------------------------------------------- #
def handle_ad(first_nodes, dry=False, max_seconds=AD_MAX_SECONDS,
              poll=DEFAULT_POLL):
    """Watch one ad and cut it the moment it can be closed.

    Returns True when the ad is gone (quiz / reward screen visible again).
    """
    t0 = time.time()
    nodes = first_nodes
    taps = 0
    last_tap = 0.0
    back_done = False
    relaunch_done = False
    last_note = 0.0

    while time.time() - t0 < max_seconds:
        if not nodes:
            nodes = dump_nodes()

        if extract_quiz(nodes):
            log("AD cleared -> quiz visible")
            return True
        if is_bot_check(nodes):
            log("BOT CHECK detected inside ad flow - pausing taps")
            return False

        # 1) a genuine close / skip button
        btn = find_close(nodes)
        if btn and btn.click:
            now = time.time()
            if now - last_tap >= 0.30:
                log(f"AD CUT -> tap '{btn.label or btn.rid or 'X'}' at {btn.click}")
                if not dry:
                    tap(*btn.click)
                taps += 1
                last_tap = now
            nodes = dump_nodes()
            continue

        # 2) an "exit ad?" confirmation dialog
        blob = all_labels(nodes, 120)
        if any(w in blob for w in ("exit ad", "leave app", "close ad?",
                                   "are you sure", "want to close", "skip ad?")):
            yes = find_button(nodes, {"yes", "exit", "leave", "close", "skip",
                                      "confirm", "ok", "okay"})
            if yes and yes.click:
                log(f"AD confirm dialog -> '{yes.label}'")
                if not dry:
                    tap(*yes.click)
                nodes = dump_nodes()
                continue

        # 3) ad opened Play Store / browser by accident
        fp = foreign_pkg(nodes)
        if fp:
            if not back_done:
                log(f"AD landed on foreign app {fp} -> BACK")
                if not dry:
                    press_back()
                back_done = True
            else:
                if not relaunch_done:
                    log("Still away from the app -> relaunching it")
                    if not dry:
                        bring_app_foreground()
                    relaunch_done = True
                else:
                    if not dry:
                        press_back()
            time.sleep(0.35)
            nodes = dump_nodes()
            continue

        # 4) not an ad any more (reward screen / quiz already handled)
        if not looks_like_ad(nodes):
            log("AD finished (non-ad screen)")
            return True

        # 5) still playing / loading -> wait for the close button
        now = time.time()
        if now - last_note > 3:
            log(f"AD playing... waiting for Close ({now - t0:.0f}s)")
            last_note = now
        time.sleep(poll)
        nodes = dump_nodes()

    log(f"AD handler timed out after {max_seconds}s")
    return False


# --------------------------------------------------------------------------- #
#  main loop
# --------------------------------------------------------------------------- #
def run(max_steps=600, dry=False, poll=DEFAULT_POLL,
        ad_max=AD_MAX_SECONDS, open_app=False):
    cfg = load_json(CONFIG_FILE, {})
    cache = normalize_cache(load_json(CACHE_FILE, {}))

    log("=" * 60)
    log("KING QUIZ BOT v2 started")
    log(f"cache entries: {len(cache)}")

    if not setup_device():
        return
    if not cfg.get("gemini_api_key"):
        log("WARNING: no gemini_api_key in ai_config.json (cache/heuristics only)")

    focus_pkg, focus_act = get_focus()
    log(f"focus: {focus_pkg}/{focus_act}")
    if QUIZ_PKG not in focus_pkg:
        if open_app and not dry:
            bring_app_foreground()
            time.sleep(2)
        else:
            log(f"WARNING: {QUIZ_PKG} is not in the foreground. Open the app first.")

    last_state = None
    last_progress = ""
    answered_sig = None
    answered_at = 0.0
    pending = None
    idle = 0
    dump_ms = 0

    for step in range(1, max_steps + 1):
        t_dump = time.time()
        nodes = dump_nodes()
        dump_ms = int((time.time() - t_dump) * 1000)
        if not nodes:
            time.sleep(0.3)
            continue

        # ---- bot check: never tap blindly
        if is_bot_check(nodes):
            log("BOT CHECK / CAPTCHA on screen - solve it on the phone; pausing")
            if step == 1 or idle == 0:
                screenshot(os.path.join(
                    BASE_DIR, f"botcheck_{time.strftime('%H%M%S')}.png"))
            idle += 1
            time.sleep(2)
            continue

        progress = get_progress(nodes)
        quiz = extract_quiz(nodes)
        bonus_btn = find_bonus(nodes) if not quiz else None
        ad = looks_like_ad(nodes)

        if pending:
            learn_feedback(nodes, pending, cache)
            if time.time() - pending["at"] > 6:
                pending = None

        if progress != last_progress:
            if last_progress:
                log(f"PROGRESS {last_progress} -> {progress}")
            last_progress = progress

        state = ("AD" if ad else
                 "QUIZ" if quiz else
                 "BONUS" if bonus_btn else
                 "COMPLETE" if is_complete(nodes, progress) else "IDLE")
        if state != last_state:
            log(f"STATE -> {state}  progress={progress or '-'}  dump={dump_ms}ms")
            last_state = state

        # ---- 1) ads always win
        if ad:
            handle_ad(nodes, dry=dry, max_seconds=ad_max, poll=poll)
            idle = 0
            continue

        # ---- 2) quiz question
        if quiz:
            sig = quiz["sig"]
            if sig == answered_sig:
                if time.time() - answered_at < SAME_QUESTION_RETRY:
                    # wait for the app to show the result / next question
                    time.sleep(0.15)
                    continue
                log("Same question still visible -> retry tap")
            log(f"QUESTION: {quiz['question']}")
            for o in quiz["options"]:
                log(f"   {o['letter']}. {o['text']}")
            entry = cache.get(qkey(quiz["question"]))
            ans, conf, _ = decide_answer(quiz["question"], quiz["options"], cfg,
                                         cache, entry)
            chosen = next((o for o in quiz["options"] if o["letter"] == ans), None)
            if not chosen:
                chosen = quiz["options"][0]
            log(f"ANSWER -> {chosen['letter']}. {chosen['text']} ({conf:.2f})")
            if not dry:
                if chosen["tap"]:
                    tap(*chosen["tap"])
                elif chosen.get("cy"):
                    tap((0 + SCREEN_W) // 2, chosen["cy"])
                pending = {"key": qkey(quiz["question"]),
                           "letter": chosen["letter"], "at": time.time()}
                answered_sig = sig
                answered_at = time.time()
                if conf < 0.9 or entry:
                    record_answer(cache, quiz, chosen, conf)
            idle = 0
            time.sleep(ACTION_SETTLE)
            continue

        # ---- 3) Add Bonus / Watch Ad
        if bonus_btn:
            log(f"BONUS button '{bonus_btn.label or bonus_btn.rid}' at {bonus_btn.click}")
            if not dry and bonus_btn.click:
                tap(*bonus_btn.click)
            idle = 0
            time.sleep(ACTION_SETTLE)
            continue

        # ---- 4) completion screen
        if is_complete(nodes, progress):
            btn = find_button(nodes, NEXT_WORDS)
            log(f"COMPLETION screen. progress={progress or '-'} "
                f"button={btn.label if btn else None}")
            if btn and not dry and btn.click:
                tap(*btn.click)
                time.sleep(0.5)
                nodes = dump_nodes()
                if extract_quiz(nodes):
                    log("A new quiz round appeared, continuing")
                    continue
            log("All tasks finished.")
            break

        # ---- 5) reward / next / continue / claim
        nxt = find_button(nodes, NEXT_WORDS)
        if nxt and nxt.click:
            log(f"NEXT button '{nxt.label}' -> tap")
            if not dry:
                tap(*nxt.click)
            idle = 0
            time.sleep(ACTION_SETTLE)
            continue

        # ---- 6) we are outside the app on some unknown screen
        fp = foreign_pkg(nodes)
        if fp:
            log(f"Foreign app in foreground ({fp}) -> BACK to quiz")
            if not dry:
                press_back()
            idle = 0
            time.sleep(0.4)
            continue

        # ---- 7) nothing actionable
        idle += 1
        if idle in (25, 60, 120):
            log(f"Waiting... no actionable element ({idle} polls). "
                f"labels={all_labels(nodes, 40)[:180]}")
            if idle == 120:
                screenshot(os.path.join(
                    BASE_DIR, f"stuck_{time.strftime('%H%M%S')}.png"))
        time.sleep(0.5)

    log("BOT stopped.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-steps", type=int, default=600)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--poll", type=float, default=DEFAULT_POLL)
    ap.add_argument("--ad-max", type=int, default=AD_MAX_SECONDS)
    ap.add_argument("--serial", default="")
    ap.add_argument("--open", action="store_true", help="bring app to foreground")
    args = ap.parse_args()
    try:
        run(max_steps=args.max_steps, dry=args.dry_run, poll=args.poll,
            ad_max=args.ad_max, open_app=args.open)
    except KeyboardInterrupt:
        log("Interrupted by user.")
