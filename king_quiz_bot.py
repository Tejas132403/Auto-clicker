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
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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
    "add bonus", "add bonus +", "watch ad", "watch ads",
    "get bonus", "claim bonus", "bonus", "extra bonus", "double reward",
}
COMPLETE_WORDS = {
    "completed", "congratulations", "all questions", "all tasks",
    "claim reward", "come back tomorrow", "quiz completed",
    "your today's limit over.", "today's limit over", "limit over", "limit reached",
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

REDIRECT_PKGS = {
    "com.android.vending",
    "com.android.chrome",
    "com.vivo.browser",
    "com.vivo.appstore",
    "com.bbk.appstore",
    "org.chromium.chrome",
    "com.google.android.googlequicksearchbox",
    "com.google.android.apps.messaging",
    "com.sec.android.app.sbrowser",
}


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
    try:
        print(line, flush=True)
    except Exception:
        try:
            print(line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace"), flush=True)
        except Exception:
            pass
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


def press_home():
    log("HOME key")
    adb(["shell", "input", "keyevent", "3"])


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
    log(f"Bringing {QUIZ_PKG} to foreground via launcher intent (preserving task state)")
    # Using monkey sends a standard launcher intent which resumes existing tasks
    # without resetting the task stack or triggering a cold restart
    adb(["shell", "monkey", "-p", QUIZ_PKG, "-c",
         "android.intent.category.LAUNCHER", "1"], timeout=10)


def get_target_recent_index(target_pkg=QUIZ_PKG):
    """Returns 0-based index of target_pkg in the OS recent tasks stack, or -1 if not found."""
    try:
        out = adb(["shell", "dumpsys", "activity", "recents"], timeout=5)
        matches = re.findall(r"Recent #(\d+): Task\{[^\n]+A=\d+:([^\s\n]+)", out)
        for idx_str, pkg in matches:
            if target_pkg in pkg:
                return int(idx_str)
    except Exception:
        pass
    return -1


def get_recents_current_label():
    """Extracts the label of the currently centered card in Vivo/Android Recents view."""
    try:
        adb(["shell", "rm", "-f", "/sdcard/rec_lbl.xml"], timeout=3)
        adb(["shell", "uiautomator", "dump", "/sdcard/rec_lbl.xml"], timeout=4)
        xml = adb(["shell", "cat", "/sdcard/rec_lbl.xml"], timeout=4)
        m = re.search(r'text="([^"]+)" resource-id="com\.vivo\.recents:id/label"', xml)
        if m:
            return m.group(1).lower().strip()
    except Exception:
        pass
    return ""


def check_resumed_focus(target_pkg, max_wait=2.5):
    """Polls focus until target_pkg is active or max_wait seconds elapse."""
    t0 = time.time()
    while time.time() - t0 < max_wait:
        p, a = get_focus()
        if target_pkg in p:
            return True, p, a
        time.sleep(0.3)
    p, a = get_focus()
    return target_pkg in p, p, a


def reopen_from_recents(target_pkg=QUIZ_PKG, app_names=("redeem code", "diamond hub", "shake master", "quiz")):
    """Reopens target_pkg from Recent Apps overview without fresh restart,
    even if many background apps/tabs are open (e.g. 3, 5, or more positions deep),
    preserving the exact in-app state, ad playback, and install tracker.
    """
    log(f"[RECENTS] Re-opening {target_pkg} from Recent Apps overview...")
    resumed, p, a = check_resumed_focus(target_pkg, max_wait=0.5)
    if resumed:
        log(f"[RECENTS] App already in foreground: {p}/{a}")
        return True

    SCREEN_W, SCREEN_H = get_screen_size()
    cy_target = int(SCREEN_H * 0.479)  # ~1150 on 2400h
    cx_center = SCREEN_W // 2           # ~540 on 1080w

    # Step 1: Check task order in dumpsys recents
    target_idx = get_target_recent_index(target_pkg)
    log(f"[RECENTS] Target {target_pkg} is at Recents index #{target_idx}")

    # Step 2: Open Recents overview
    adb(["shell", "input", "keyevent", "187"])
    time.sleep(0.8)

    # Step 3: Check currently centered card in Recents
    lbl = get_recents_current_label()
    if lbl and any(k in lbl for k in app_names):
        log(f"[RECENTS] Target card '{lbl}' is already centered -> tapping to resume!")
        tap(cx_center, cy_target)
        resumed, p, a = check_resumed_focus(target_pkg)
        if resumed:
            log(f"[RECENTS] Successfully resumed {target_pkg} ({p}/{a})")
            return True

    # Step 4: Swipe cards to navigate to target
    # If target_idx is known, swipe right to navigate towards older cards
    # On Vivo launcher: swipe 400 1200 700 1200 400 moves 1 card left/older
    # swipe 700 1200 400 1200 400 moves 1 card right/newer
    swipes_to_try = max(1, target_idx) if target_idx > 0 else 6
    log(f"[RECENTS] Navigating up to {swipes_to_try} card steps...")

    for step in range(swipes_to_try + 2):
        lbl = get_recents_current_label()
        if lbl and any(k in lbl for k in app_names):
            log(f"[RECENTS] Step {step + 1}: Found target card '{lbl}' centered! Tapping snapshot...")
            tap(cx_center, cy_target)
            resumed, p, a = check_resumed_focus(target_pkg)
            if resumed:
                log(f"[RECENTS] Successfully resumed {target_pkg} ({p}/{a})")
                return True

        # Perform one-card swipe (300px step: 400 -> 700)
        log(f"[RECENTS] Step {step + 1}: Current card '{lbl}' -> Swiping 1 card to find target...")
        adb(["shell", "input", "swipe", "400", str(cy_target), "700", str(cy_target), "400"])
        time.sleep(0.6)

    # Step 5: Tap whatever is centered and verify focus
    log(f"[RECENTS] Tapping center snapshot at ({cx_center}, {cy_target})...")
    tap(cx_center, cy_target)
    resumed, p, a = check_resumed_focus(target_pkg)
    if resumed:
        log(f"[RECENTS] Resumed {target_pkg} ({p}/{a})")
        return True

    # Step 6: If still not in target, try swiping in reverse direction
    log(f"[RECENTS] Retrying reverse direction...")
    for retry in range(4):
        adb(["shell", "input", "keyevent", "187"])
        time.sleep(0.8)
        lbl = get_recents_current_label()
        if lbl and any(k in lbl for k in app_names):
            tap(cx_center, cy_target)
            resumed, p, a = check_resumed_focus(target_pkg)
            if resumed:
                log(f"[RECENTS] Successfully resumed {target_pkg} ({p}/{a})")
                return True
        adb(["shell", "input", "swipe", "700", str(cy_target), "400", str(cy_target), "400"])
        time.sleep(0.6)
        tap(cx_center, cy_target)
        resumed, p, a = check_resumed_focus(target_pkg)
        if resumed:
            log(f"[RECENTS] Successfully resumed {target_pkg} ({p}/{a})")
            return True

    # Step 7: Final safe resume via monkey (resumes existing task stack without cold restart)
    log(f"[RECENTS] Safe resume via launcher intent (preserves activity stack)...")
    adb(["shell", "monkey", "-p", target_pkg, "-c", "android.intent.category.LAUNCHER", "1"])
    resumed, p, a = check_resumed_focus(target_pkg, max_wait=3.0)
    log(f"[RECENTS] Final focus: {p}/{a}")
    return resumed


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
    """Dump + fetch in ONE adb round-trip with fast timeout to avoid UI lock."""
    cmd = (f"rm -f {TMP_XML}; uiautomator dump {TMP_XML} "
           f">/dev/null 2>&1; cat {TMP_XML} 2>/dev/null")
    out = adb(["shell", cmd], timeout=6)
    if "<hierarchy" in out:
        return out
    return ""


def dump_nodes():
    """Return list[Node] for the current screen, or [] on failure."""
    txt = ""
    for attempt in range(2):
        try:
            txt = _read_hierarchy()
        except Exception as e:
            log(f"dump error: {e}")
            txt = ""
        if "<hierarchy" in txt:
            break
        time.sleep(0.1)

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
        if "add bonus" in t or "watch ad" in t or "claim bonus" in t:
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
    # If we are inside one of our app's normal screens, ignore embedded native banners
    if QUIZ_PKG in focus_pkg and any(act in focus_act.lower() for act in ("watchandearnactivity", "quizactivity", "mainactivity")):
        for n in nodes:
            r = (n.rid or "").lower()
            if any(m in r for m in ("app-interstitial-slot", "mys-creative", "mys-wrapper")):
                return True
        return False

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
    if any(w in labels for w in COMPLETE_WORDS) or by_rid(nodes, "limit_layout") or by_rid(nodes, "limit_text"):
        return True
    m = re.match(r"(\d+)/(\d+)", (progress or "").replace(" ", ""))
    if m and int(m.group(1)) >= int(m.group(2)) > 0:
        return True
    return False


def is_bot_check(nodes):
    labels = all_labels(nodes, 120)
    return any(w in labels for w in BOT_CHECK_WORDS)


# --------------------------------------------------------------------------- #
#  Home & Activity navigation helpers
# --------------------------------------------------------------------------- #
def is_home_screen(nodes, focus_act=""):
    if "MainActivity" in focus_act:
        return True
    if by_rid(nodes, "mainPager") or by_rid(nodes, "cl_daily_hub"):
        return True
    return False


def is_quiz_screen(nodes, focus_act=""):
    if "QuizActivity" in focus_act:
        return True
    if by_rid(nodes, "tvQuestion") or by_rid(nodes, "tvOptionText"):
        return True
    return False


def is_watch_screen(nodes, focus_act=""):
    if "WatchAndEarnActivity" in focus_act:
        return True
    if by_rid(nodes, "btn_watch_now") or by_rid(nodes, "textRemaining"):
        return True
    return False


def find_quiz_card(nodes):
    """Find strictly the Quiz section card on the Home screen."""
    card = by_rid(nodes, "clQuiz")
    if card and card.click:
        return card
    for n in nodes:
        if "clquiz" in (n.rid or "").lower() and n.click:
            return n
    return None


def find_watch_video_card(nodes):
    """Find strictly the Watch Video task card on the Home screen."""
    card = by_rid(nodes, "clWatchVideo")
    if card and card.click:
        return card
    for n in nodes:
        if "clwatchvideo" in (n.rid or "").lower() and n.click:
            return n
    for n in nodes:
        if n.label.strip().lower() == "watch video" and n.click:
            return n
    return None


def scroll_to_top():
    """Scroll content down (swipe finger down), bringing top items (Quiz) into view."""
    adb(["shell", "input", "swipe", "540", "600", "540", "1800", "250"])
    time.sleep(0.4)


def scroll_down_screen():
    """Scroll content up (swipe finger up), bringing lower items (Watch Video) into view."""
    adb(["shell", "input", "swipe", "540", "1800", "540", "600", "250"])
    time.sleep(0.4)


scroll_down = scroll_down_screen


def get_watch_progress(nodes):
    """Parse video watch count, e.g. 0 / 20."""
    rem = by_rid(nodes, "progress_remaining_count")
    tot = by_rid(nodes, "progress_count")
    rem_txt = (rem.text if rem else "").replace("/", "").strip()
    tot_txt = (tot.text if tot else "").strip()
    cur_val, tot_val = None, None
    try:
        cur_val = int(rem_txt)
    except Exception:
        pass
    try:
        tot_val = int(tot_txt)
    except Exception:
        pass
    p_str = f"{rem_txt}/{tot_txt}" if (rem_txt or tot_txt) else ""
    return cur_val, tot_val, p_str


def is_watch_complete(nodes):
    """Check if all video watch tasks are completed."""
    cur, tot, _ = get_watch_progress(nodes)
    if cur is not None and tot is not None and cur >= tot > 0:
        return True
    rem_label = by_rid(nodes, "textRemaining")
    if rem_label and rem_label.text:
        txt = rem_label.text.lower()
        if re.search(r"\b0\s+more\s+videos\b", txt) or re.search(r"\bwatch\s+0\s+more\b", txt):
            return True
    labels = all_labels(nodes, 80).lower()
    if "come back tomorrow" in labels or "limit reached" in labels:
        return True
    return False


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
    configured = [cfg.get("quiz_model"), cfg.get("gemini_model")]
    fallbacks = cfg.get("gemini_fallback_models") or [
        "gemini-flash-lite-latest",
        "gemini-3.1-pro-preview",
        "gemini-pro-latest"
    ]
    for m in configured + fallbacks:
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


def ask_ollama(question, options, cfg):
    """Fallback to local Ollama (llama3.2) if Gemini is offline or rate-limited."""
    host = cfg.get("ollama_host", "http://127.0.0.1:11434")
    model = cfg.get("ollama_model", "llama3.2:latest")
    prompt = (
        f"You are an expert at mobile video games, specifically Free Fire.\n"
        f"Answer this quiz question accurately.\n\n"
        f"Question: {question}\n\n"
        f"Options:\n"
    )
    for o in options:
        prompt += f"{o['letter']}. {o['text']}\n"
    prompt += (
        f"\nWhich option is correct? Respond ONLY with JSON like {{\"answer\": \"A\"}}. No explanations."
    )
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0}
    }).encode("utf-8")
    req = urllib.request.Request(f"{host}/api/generate", data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            raw = data.get("response", "")
            ans, conf = parse_answer(raw, options)
            if ans:
                log(f"OLLAMA[{model}] (Fallback) -> {ans} (conf {conf:.2f})")
                return ans, 0.75
    except Exception as e:
        log(f"OLLAMA fallback error: {e}")
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
        (("बिना खेले", "spectate", "देखने"), ("spectate",)),
    ]
    for qkeys, akeys in rules:
        if any(k in q for k in qkeys):
            for o in options:
                if any(a in o["text"].lower() for a in akeys):
                    return o["letter"], 0.4
    return None, 0.0


def decide_answer(question, options, cfg, cache, entry=None):
    # 1. Check local cache first: if repeated question, answer instantly from cache
    letter, hit, score = cache_lookup(cache, question, options)
    if letter:
        wrong = [str(w).upper() for w in (hit.get("wrong") or [])]
        if letter not in wrong:
            ans_text = hit.get("answer_text") or (hit.get("options") or {}).get(letter, "")
            log(f"CACHE HIT ({score:.2f}) -> {letter}. {ans_text} [Repeated Question, answered locally]")
            return letter, 1.0, hit
        log(f"CACHE hit but {letter} is blacklisted, asking Gemini...")

    # 2. If question is NEW, ask Gemini
    log(f"[NEW QUESTION] Asking Gemini for answer...")
    ans, conf = ask_gemini(question, options, cfg)
    if ans:
        # Save Gemini's answer to local cache for future repeated questions
        chosen_opt = next((o for o in options if o["letter"] == ans), None)
        record_answer(cache, {"question": question, "options": options},
                      chosen_opt or {"letter": ans, "text": ""}, conf, source="GEMINI")
        return ans, conf, hit

    # 3. If Gemini is rate-limited or fails, fallback to local Ollama
    log("Gemini rate-limited/failed -> falling back to local Ollama...")
    ans, conf = ask_ollama(question, options, cfg)
    if ans:
        chosen_opt = next((o for o in options if o["letter"] == ans), None)
        record_answer(cache, {"question": question, "options": options},
                      chosen_opt or {"letter": ans, "text": ""}, conf, source="OLLAMA")
        return ans, conf, hit

    # 4. Local Free Fire Keyword Heuristic
    log("Ollama failed -> trying local Free Fire keyword heuristic...")
    ans, conf = local_guess(question, options)
    if ans:
        return ans, conf, entry

    # 5. Fallback to first non-blacklisted option
    wrong = [str(w).upper() for w in ((entry or {}).get("wrong") or [])]
    pool = [o for o in options if o["letter"] not in wrong] or options
    ans, conf = pool[0]["letter"], 0.1
    log(f"FALLBACK first option -> {ans}")
    return ans, conf, entry


def record_answer(cache, quiz, chosen, conf, source="GEMINI"):
    """Store answer locally in quiz_answers.json so repeated questions are answered instantly."""
    key = qkey(quiz["question"])
    entry = cache.get(key) or {}
    entry.update({
        "question": quiz["question"],
        "options": {o["letter"]: o["text"] for o in quiz["options"]},
        "answer": chosen["letter"],
        "answer_text": chosen.get("text", "") or (quiz.get("options", {}).get(chosen["letter"], "") if isinstance(quiz.get("options"), dict) else ""),
        "confidence": conf,
        "source": source,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    cache[key] = entry
    save_json(CACHE_FILE, cache)
    log(f"LOCAL CACHE SAVED [{source}] -> '{chosen['letter']}. {entry['answer_text']}' stored for repeat questions")
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
        entry.pop("answer", None)
        entry.pop("answer_text", None)
        entry["correct"] = False
        entry["confidence"] = 0.0
        entry["last_wrong"] = pending["letter"]
        log(f"LEARN: '{pending['letter']}' marked WRONG and blacklisted")
    else:
        entry["answer"] = pending["letter"]
        entry["answer_text"] = entry.get("options", {}).get(pending["letter"], "")
        entry["correct"] = True
        entry["confidence"] = 1.0
        log(f"LEARN: '{pending['letter']}' confirmed CORRECT")
    save_json(CACHE_FILE, cache)
    save_json(CACHE_FILE, cache)


# --------------------------------------------------------------------------- #
#  ad handling
# --------------------------------------------------------------------------- #
def handle_ad(first_nodes, dry=False, max_seconds=AD_MAX_SECONDS,
              poll=DEFAULT_POLL):
    """Watch ad and cut it the instant it can be skipped or dismissed.
    Uses active corner taps and back-key triggering after minimum duration.
    """
    t0 = time.time()
    nodes = first_nodes
    last_tap = 0.0
    back_done = False
    relaunch_done = False
    last_note = 0.0
    last_cut_attempt = 0.0

    def is_back_in_app(p, a):
        if QUIZ_PKG in p and ("quizactivity" in a.lower() or "watch" in a.lower() or "mainactivity" in a.lower()):
            return True
        if p in REDIRECT_PKGS:
            press_back()
            time.sleep(0.25)
            p2, a2 = get_focus()
            return QUIZ_PKG in p2
        return False

    while time.time() - t0 < max_seconds:
        elapsed = time.time() - t0

        # Fast screen focus check (only 50ms, never blocks on video animations)
        focus_pkg, focus_act = get_focus()
        in_ad = any(m in f"{focus_pkg}/{focus_act}".lower() for m in ("gms.ads", "adactivity", "ads.adactivity"))
        if not in_ad and QUIZ_PKG in focus_pkg and ("quizactivity" in focus_act.lower() or "watch" in focus_act.lower() or "mainactivity" in focus_act.lower()):
            log(f"AD CLOSED in {elapsed:.1f}s -> focus returned to {focus_act}")
            return True

        # FAST REDIRECT INTERCEPTOR: If an ad redirected to Play Store, Chrome, or browser, dismiss immediately!
        if focus_pkg in REDIRECT_PKGS or (focus_pkg and focus_pkg != QUIZ_PKG and focus_pkg not in SYSTEM_PKGS and "launcher" not in focus_pkg):
            log(f"[REDIRECT INTERCEPTED] Ad opened {focus_pkg}/{focus_act} -> closing with BACK")
            press_back()
            time.sleep(0.25)
            p_cur, a_cur = get_focus()
            if p_cur in REDIRECT_PKGS:
                press_back()
                time.sleep(0.25)
                p_cur, a_cur = get_focus()
            if QUIZ_PKG in p_cur:
                log(f"[REDIRECT RESOLVED] Returned to {p_cur}/{a_cur}")
                continue
            elif "launcher" in p_cur:
                log(f"[REDIRECT RESOLVED] At launcher -> resuming {QUIZ_PKG} via recents")
                reopen_from_recents(QUIZ_PKG)
                continue

        # When inside an ad, NEVER block on dump_nodes() because video animations lock accessibility
        if in_ad:
            if elapsed >= 0.05 and (time.time() - last_cut_attempt >= 0.5):
                last_cut_attempt = time.time()
                log(f"AD INSTANT SKIP attempt ({elapsed:.1f}s)... pressing BACK & corners")
                if not dry:
                    # 1. Tap Android BACK key immediately (instant dismiss)
                    press_back()
                    time.sleep(0.12)
                    p, a = get_focus()
                    if is_back_in_app(p, a):
                        log(f"AD CUT SUCCESS (instant BACK key) in {time.time() - t0:.1f}s!")
                        return True

                    # 2. Tap Top-Right corner (standard AdMob / Unity close X)
                    tap(SCREEN_W - 65, 130)
                    time.sleep(0.12)
                    p, a = get_focus()
                    if is_back_in_app(p, a):
                        log(f"AD CUT SUCCESS (top-right tap) in {time.time() - t0:.1f}s!")
                        return True

                    # 3. Tap Top-Left corner (alternative close X)
                    tap(65, 130)
                    time.sleep(0.12)
                    p, a = get_focus()
                    if is_back_in_app(p, a):
                        log(f"AD CUT SUCCESS (top-left tap) in {time.time() - t0:.1f}s!")
                        return True

                    # 4. Tap Top-Right secondary offset (close button slightly indented)
                    tap(SCREEN_W - 100, 150)
                    time.sleep(0.12)
                    p, a = get_focus()
                    if is_back_in_app(p, a):
                        log(f"AD CUT SUCCESS (top-right secondary tap) in {time.time() - t0:.1f}s!")
                        return True

            time.sleep(0.35)
            continue

        # If not in AdActivity, we can safely check nodes
        if not nodes:
            nodes = dump_nodes()

        if extract_quiz(nodes):
            log(f"AD CLOSED in {elapsed:.1f}s -> quiz visible")
            return True
        if by_rid(nodes, "btn_watch_now") or by_rid(nodes, "textRemaining"):
            log(f"AD CLOSED in {elapsed:.1f}s -> watch video screen visible")
            return True
        if is_bot_check(nodes):
            log("BOT CHECK detected inside ad flow - pausing taps")
            return False

        # 1) A genuine close / skip / X button detected in UI tree
        btn = find_close(nodes)
        if btn and btn.click:
            now = time.time()
            if now - last_tap >= 0.25:
                log(f"AD CUT [UI Button] -> tap '{btn.label or btn.rid or 'X'}' at {btn.click} ({elapsed:.1f}s)")
                if not dry:
                    tap(*btn.click)
                last_tap = now
                time.sleep(0.3)
            nodes = dump_nodes()
            continue

        # 2) An "exit ad?" confirmation dialog
        blob = all_labels(nodes, 120)
        if any(w in blob for w in ("exit ad", "leave app", "close ad?",
                                   "are you sure", "want to close", "skip ad?", "resume video")):
            yes = find_button(nodes, {"yes", "exit", "leave", "close", "skip",
                                      "confirm", "ok", "okay", "close ad"})
            if yes and yes.click:
                log(f"AD confirm dialog -> tap '{yes.label}' ({elapsed:.1f}s)")
                if not dry:
                    tap(*yes.click)
                time.sleep(0.3)
                nodes = dump_nodes()
                continue

        # 3) Ad opened Play Store / browser by accident
        fp = foreign_pkg(nodes)
        if fp:
            if not back_done:
                log(f"AD landed on foreign app {fp} -> BACK")
                if not dry:
                    press_back()
                back_done = True
            else:
                if not relaunch_done:
                    log("Still away from the app -> resuming via recents")
                    if not dry:
                        reopen_from_recents(QUIZ_PKG)
                    relaunch_done = True
                else:
                    if not dry:
                        press_back()
            time.sleep(0.35)
            nodes = dump_nodes()
            continue

        # 4) Not an ad anymore
        if not in_ad and not looks_like_ad(nodes, focus_pkg, focus_act):
            log(f"AD finished in {elapsed:.1f}s (non-ad screen)")
            return True

        time.sleep(poll)
        nodes = dump_nodes()
        nodes = dump_nodes()

    log(f"AD handler finished after {time.time() - t0:.1f}s")
    return False


DUMMY_APK = os.path.join(BASE_DIR, "in.binarybox.blackscreen for ad installation.apk")
DUMMY_PKG = "in.binarybox.blackscreen"

APP_NAME_PREFIXES = ["CleanMaster", "SpeedBooster", "GameVault", "ProScanner", "FlashLight", "BatterySaver", "TurboVpn", "ColorNotes", "SuperClean", "RamBooster"]
APP_DOMAINS = ["com.cleaner", "com.boost", "com.vault", "com.utility", "com.turbo", "com.mobile", "com.smart", "com.fast"]


def generate_unique_dummy_apk():
    """Dynamically mutates the genuine black screen app's package name and app label
    in-place so that Android resources, activities, and layouts are 100% intact,
    preventing any auto-close/crashes, while generating an entirely new Package Name
    and App Name on each install task.
    """
    if not os.path.exists(DUMMY_APK):
        return DUMMY_APK, DUMMY_PKG, "Dummy App"

    sdk_dir = os.path.expandvars(r'%LOCALAPPDATA%\Android\Sdk')
    build_tools_dir = os.path.join(sdk_dir, 'build-tools')
    if not os.path.isdir(build_tools_dir):
        return DUMMY_APK, DUMMY_PKG, "Dummy App"

    bt_versions = sorted(os.listdir(build_tools_dir), reverse=True)
    if not bt_versions:
        return DUMMY_APK, DUMMY_PKG, "Dummy App"
    build_tools = os.path.join(build_tools_dir, bt_versions[0])
    apksigner = os.path.join(build_tools, 'apksigner.bat' if os.name == 'nt' else 'apksigner')
    keystore = os.path.expandvars(r'%USERPROFILE%\.android\debug.keystore')

    if not (os.path.exists(apksigner) and os.path.exists(keystore)):
        return DUMMY_APK, DUMMY_PKG, "Dummy App"

    import random
    import string
    import shutil
    import zipfile

    # Generate unique 24-character package name (exact match to 'in.binarybox.blackscreen')
    rand_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    new_pkg = f"com.boxapp.blackscr_{rand_id}"
    assert len(new_pkg) == len("in.binarybox.blackscreen")

    # Generate unique 12-character app label (exact match to 'Black Screen')
    labels = ["Game Booster", "Fast Cleaner", "Power Boost ", "Clean Master", "Turbo Clean ", "Super Saver "]
    new_label = random.choice(labels)
    assert len(new_label) == len("Black Screen")

    build_dir = os.path.join(BASE_DIR, "tmp_build")
    os.makedirs(build_dir, exist_ok=True)
    out_apk = os.path.join(build_dir, f"{new_pkg}.apk")
    if os.path.exists(out_apk):
        try:
            os.remove(out_apk)
        except Exception:
            pass

    old_pkg_bytes = "in.binarybox.blackscreen".encode("utf-16le")
    new_pkg_bytes = new_pkg.encode("utf-16le")
    old_lbl_bytes = b"Black Screen"
    new_lbl_bytes = new_label.encode("utf-8")

    try:
        with zipfile.ZipFile(DUMMY_APK, "r") as zin:
            manifest = zin.read("AndroidManifest.xml")
            pos_pkg = manifest.find(old_pkg_bytes)
            if pos_pkg != -1:
                new_manifest = manifest[:pos_pkg] + new_pkg_bytes + manifest[pos_pkg + len(old_pkg_bytes):]
            else:
                new_manifest = manifest

            arsc = zin.read("resources.arsc")
            pos_lbl = arsc.find(old_lbl_bytes)
            if pos_lbl != -1:
                new_arsc = arsc[:pos_lbl] + new_lbl_bytes + arsc[pos_lbl + len(old_lbl_bytes):]
            else:
                new_arsc = arsc

            with zipfile.ZipFile(out_apk, "w", compression=zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename.startswith("META-INF/"):
                        continue  # Strip old signatures
                    if item.filename == "AndroidManifest.xml":
                        zout.writestr(item, new_manifest)
                    elif item.filename == "resources.arsc":
                        zout.writestr(item, new_arsc)
                    else:
                        zout.writestr(item, zin.read(item.filename))

        # Sign modified APK with debug keystore
        cmd_sign = [
            apksigner, "sign",
            "--ks", keystore,
            "--ks-pass", "pass:android",
            "--key-pass", "pass:android",
            "--ks-key-alias", "androiddebugkey",
            out_apk
        ]
        res_sign = subprocess.run(cmd_sign, capture_output=True, text=True)
        if res_sign.returncode != 0:
            log(f"[APK-GEN] apksigner error: {res_sign.stderr}")
            return DUMMY_APK, DUMMY_PKG, "Dummy App"

        return out_apk, new_pkg, new_label
    except Exception as e:
        log(f"[APK-GEN] Error creating unique APK: {e}")
        return DUMMY_APK, DUMMY_PKG, "Dummy App"


def _background_uninstall_worker(pkg, delay):
    """Background worker that waits delay seconds and silently uninstalls the dummy app via ADB."""
    time.sleep(delay)
    log(f"[AUTO-DELETE] 1 minute elapsed -> silently uninstalling '{pkg}' in background...")
    res = adb(["uninstall", pkg], timeout=20)
    log(f"[AUTO-DELETE] App '{pkg}' background uninstall result: {res.strip() if res else 'OK'}")


def schedule_delayed_uninstall(pkg=DUMMY_PKG, delay_seconds=60):
    """Schedules dummy app deletion after 1 minute in a daemon thread so quiz workflow is NOT disturbed."""
    t = threading.Thread(
        target=_background_uninstall_worker,
        args=(pkg, delay_seconds),
        daemon=True,
        name=f"DelayedUninstall-{pkg}"
    )
    t.start()
    log(f"[AUTO-DELETE] Scheduled background deletion of '{pkg}' in {delay_seconds}s (workflow undisturbed).")


def execute_full_install_sequence(dry=False, ad_max=AD_MAX_SECONDS, poll=DEFAULT_POLL):
    """Executes the exact 4th-attempt Install Task flow specified by user:
    give ans > add bonus > ad load > go to mobile home screen > install app >
    open it > wait for 10 second > back to mobile home screen > from recent app open my app >
    then cut ads > then you again see add bonus > after 1 min install app delete automatically
    """
    log("=" * 65)
    log("[INSTALL TASK] 4th Repeat Triggered: Starting App Install Sequence!")
    log("=" * 65)

    # 1. Wait for ad to load on screen (AdActivity)
    t_start = time.time()
    ad_loaded = False
    while time.time() - t_start < 8.0:
        p, a = get_focus()
        if any(m in f"{p}/{a}".lower() for m in ("gms.ads", "adactivity", "ads.adactivity")):
            log(f"[INSTALL TASK] Ad loaded ({p}/{a})")
            ad_loaded = True
            break
        time.sleep(0.4)
    if not ad_loaded:
        log("[INSTALL TASK] Ad didn't open in 8s -> continuing install flow anyway")

    # 2. Go to mobile Home screen
    log("[INSTALL TASK] Step 1: Going to Mobile Home screen...")
    press_home()
    time.sleep(1.0)

    # 3. Generate a dynamically unique APK with fresh Package Name, App Label & ID
    target_apk, target_pkg, target_label = generate_unique_dummy_apk()
    log(f"[INSTALL TASK] Step 2: Generated unique app '{target_label}' (pkg: {target_pkg})")
    log(f"[INSTALL TASK] Installing unique APK via ADB...")
    res = adb(["install", "-r", "-g", target_apk])
    log(f"[INSTALL TASK] Install status: {res.strip() if res else 'OK'}")

    # 4. Open the uniquely installed app
    log(f"[INSTALL TASK] Step 3: Opening {target_pkg} (MainActivity)...")
    adb(["shell", "am", "start", "-n", f"{target_pkg}/in.binarybox.blackscreen.MainActivity"])

    # 5. Wait for 10 seconds inside dummy app
    log(f"[INSTALL TASK] Step 4: Waiting for 10 seconds inside '{target_label}'...")
    time.sleep(10.0)

    # 6. Back to mobile Home screen
    log("[INSTALL TASK] Step 5: Returning to Mobile Home screen...")
    press_home()
    time.sleep(1.0)

    # 7. From recent apps open my app
    log(f"[INSTALL TASK] Step 6: Re-opening {QUIZ_PKG} from recent apps (preserving task state)...")
    reopen_from_recents(QUIZ_PKG)
    time.sleep(1.2)

    # 8. Cut ads
    log("[INSTALL TASK] Step 7: Cutting ad now...")
    handle_ad(None, dry=dry, max_seconds=ad_max, poll=poll)
    time.sleep(1.0)

    # 9. Check if 'Add Bonus' is visible again and tap it (poll for up to 3s)
    bonus_clicked = False
    for _ in range(5):
        nodes = dump_nodes()
        bonus_btn = find_bonus(nodes)
        if bonus_btn and bonus_btn.click:
            log(f"[INSTALL TASK] Step 8: 'Add Bonus' visible -> tapping at {bonus_btn.click}")
            if not dry:
                tap(*bonus_btn.click)
                time.sleep(1.0)
                handle_ad(None, dry=dry, max_seconds=ad_max, poll=poll)
            bonus_clicked = True
            break
        claim = find_button(nodes, {"claim", "continue", "next", "ok", "okay", "done", "verify"})
        if claim and claim.click:
            log(f"[INSTALL TASK] Step 8b: Tapping completion button '{claim.label}' at {claim.click}")
            if not dry:
                tap(*claim.click)
                time.sleep(1.0)
            bonus_clicked = True
            break
        time.sleep(0.5)

    # 10. Auto-delete installed app after 1 minute in background
    schedule_delayed_uninstall(target_pkg, delay_seconds=60)
    log(f"[INSTALL TASK] Step 9: Install task 100% complete! Auto-delete of '{target_pkg}' in 1 min scheduled.")
    log("=" * 65)


def perform_fake_install_bypass():
    execute_full_install_sequence()


# --------------------------------------------------------------------------- #
#  main loop
# --------------------------------------------------------------------------- #
def run(task="all", max_steps=1000, dry=False, poll=DEFAULT_POLL,
        ad_max=AD_MAX_SECONDS, open_app=False):
    cfg = load_json(CONFIG_FILE, {})
    cache = normalize_cache(load_json(CACHE_FILE, {}))

    log("=" * 60)
    log(f"KING AUTOMATION BOT v2 started (Task Mode: {task.upper()})")
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

    phase = "WATCH_VIDEO" if task == "video" else "QUIZ"
    last_progress = ""
    last_completed_progress = None
    same_progress_count = 0
    last_watch_p_str = ""
    last_watch_completed_progress = None
    same_video_count = 0
    answered_sig = None
    answered_at = 0.0
    pending = None
    idle = 0
    dump_ms = 0
    home_scroll_count = 0
    same_q_count = 0

    for step in range(1, max_steps + 1):
        focus_pkg, focus_act = get_focus()
        in_ad = any(m in f"{focus_pkg}/{focus_act}".lower() for m in ("gms.ads", "adactivity", "ads.adactivity"))
        if in_ad:
            handle_ad(None, dry=dry, max_seconds=ad_max, poll=poll)
            idle = 0
            continue

        # Fast Foreign App / Redirect Dismissal (e.g. Play Store, Chrome browser, etc.)
        if focus_pkg and QUIZ_PKG not in focus_pkg:
            if focus_pkg in REDIRECT_PKGS or (focus_pkg not in SYSTEM_PKGS and focus_pkg != QUIZ_PKG):
                log(f"[FOREIGN REDIRECT] {focus_pkg}/{focus_act} detected -> pressing BACK to return to {QUIZ_PKG}")
                press_back()
                time.sleep(0.3)
                p2, a2 = get_focus()
                if p2 in REDIRECT_PKGS:
                    press_back()
                    time.sleep(0.3)
                    p2, a2 = get_focus()
                if QUIZ_PKG not in p2:
                    if "launcher" in p2:
                        reopen_from_recents(QUIZ_PKG)
                    else:
                        press_back()
                idle = 0
                continue

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

        # ---- foreign app (Play Store, browser, launcher, etc.)
        fp = foreign_pkg(nodes)
        if fp:
            log(f"Foreign app in foreground ({fp}) -> BACK to app")
            if not dry:
                press_back()
            idle = 0
            time.sleep(0.4)
            continue

        # ---- 1) ads always win (highest priority)
        ad = looks_like_ad(nodes, focus_pkg, focus_act)
        if ad:
            handle_ad(nodes, dry=dry, max_seconds=ad_max, poll=poll)
            idle = 0
            continue

        # =================================================================== #
        # Screen Branch 1: HOME SCREEN (MainActivity)
        # STRICT RULE: ONLY click Quiz (Phase 1) or Watch Video (Phase 2).
        # NEVER CLICK Daily Bonus, Offerwall, Streak, Socials, etc.
        # =================================================================== #
        if is_home_screen(nodes, focus_act):
            idle = 0
            if phase == "QUIZ":
                quiz_card = find_quiz_card(nodes)
                if quiz_card and quiz_card.click:
                    log(f"[HOME] Strictly entering QUIZ section (clQuiz) at {quiz_card.click}. Other sections ignored.")
                    if not dry:
                        tap(*quiz_card.click)
                    home_scroll_count = 0
                    time.sleep(1.5)
                    continue
                else:
                    home_scroll_count += 1
                    log(f"[HOME] Quiz section not visible -> scrolling up to top (attempt {home_scroll_count})...")
                    if not dry:
                        scroll_to_top()
                    if home_scroll_count > 4:
                        log("[HOME] Waiting for Quiz section to appear...")
                        time.sleep(1.0)
                    continue

            elif phase == "WATCH_VIDEO":
                watch_card = find_watch_video_card(nodes)
                if watch_card and watch_card.click:
                    log(f"[HOME] Entering WATCH VIDEO task (clWatchVideo) at {watch_card.click}. Other sections strictly forbidden.")
                    if not dry:
                        tap(*watch_card.click)
                    home_scroll_count = 0
                    time.sleep(1.5)
                    continue
                else:
                    home_scroll_count += 1
                    log(f"[HOME] Watch Video card not visible -> scrolling down (attempt {home_scroll_count})...")
                    if not dry:
                        scroll_down_screen()
                    if home_scroll_count > 6:
                        log("[HOME] Waiting for Watch Video card to appear...")
                        time.sleep(1.0)
                    continue

        # =================================================================== #
        # Screen Branch 2: QUIZ SCREEN (QuizActivity)
        # =================================================================== #
        if is_quiz_screen(nodes, focus_act):
            progress = get_progress(nodes)
            quiz = extract_quiz(nodes)
            bonus_btn = find_bonus(nodes) if not quiz else None

            # 1. Countdown timer
            timer = by_rid(nodes, "timerText")
            if timer and timer.text and "wait" in timer.text.lower():
                log(f"[QUIZ] Countdown: {timer.text}")
                time.sleep(1.0)
                continue

            # 2. Check for install app task requirement in Quiz
            blob = all_labels(nodes, 80).lower()
            install_kw = (
                "install app", "install and open", "app install task", "install this app",
                "install & earn", "install to unlock", "click on ad and install", "download app",
                "install and get", "install bonus", "install task"
            )
            if not quiz and (any(k in blob for k in install_kw) or by_text(nodes, "install")):
                log("[QUIZ] In-quiz App Install Dialog detected! Running install bypass...")
                perform_fake_install_bypass()
                continue

            # 3. Intermediate loading spinner dialog (only when no quiz and no bonus button)
            if not quiz and not bonus_btn and by_rid(nodes, "progressBar"):
                log("[QUIZ] Loading spinner (progressBar) active... waiting 1.2s")
                time.sleep(1.2)
                continue

            if pending:
                learn_feedback(nodes, pending, cache)
                if time.time() - pending["at"] > 6:
                    pending = None

            if progress != last_progress:
                if last_progress:
                    log(f"QUIZ PROGRESS: {last_progress} -> {progress}")
                last_progress = progress

            # Check if quiz is finished or round is complete
            if is_complete(nodes, progress) or (phase == "WATCH_VIDEO"):
                log(f"[QUIZ COMPLETE] Progress: {progress or '25/25'}. Returning to Home screen...")
                nxt = find_button(nodes, NEXT_WORDS)
                if nxt and not dry and nxt.click:
                    tap(*nxt.click)
                    time.sleep(0.5)
                if not dry:
                    press_back()
                phase = "WATCH_VIDEO"
                time.sleep(1.0)
                if task == "quiz":
                    log("Quiz task complete. Exiting (--task quiz specified).")
                    break
                continue

            # Answer quiz question
            if quiz:
                sig = quiz["sig"]
                # Detect repeat: either same question sitting unprogressed OR same progress number observed 3 times
                is_task_repeated = False
                if sig == answered_sig:
                    if time.time() - answered_at < SAME_QUESTION_RETRY:
                        time.sleep(0.15)
                        continue
                    same_q_count += 1
                    log(f"[QUIZ] Question repeated (count {same_q_count}/3)")
                    if same_q_count >= 3:
                        is_task_repeated = True
                else:
                    same_q_count = 0

                if same_progress_count >= 3:
                    is_task_repeated = True

                if is_task_repeated:
                    log(f"[QUIZ] Task repeated 3 times (Progress: {progress}) -> THIS IS AN INSTALL TASK!")
                    log("[INSTALL TASK] 4th attempt: Answer -> Add Bonus -> Ad Load -> Install Dummy App -> Open 10s -> Reopen from Recents -> Cut Ad -> Add Bonus...")
                    entry = cache.get(qkey(quiz["question"]))
                    ans, conf, _ = decide_answer(quiz["question"], quiz["options"], cfg, cache, entry)
                    chosen = next((o for o in quiz["options"] if o["letter"] == ans), None) or quiz["options"][0]
                    if not dry:
                        if chosen.get("tap"):
                            tap(*chosen["tap"])
                        elif chosen.get("cy"):
                            tap((0 + SCREEN_W) // 2, chosen["cy"])
                        time.sleep(1.2)

                        # Tap Add Bonus to trigger Ad
                        post_nodes = dump_nodes()
                        bonus_btn = find_bonus(post_nodes)
                        if bonus_btn and bonus_btn.click:
                            log(f"[INSTALL TASK] Tapping 'Add Bonus' at {bonus_btn.click} to trigger Ad...")
                            tap(*bonus_btn.click)
                            time.sleep(1.0)

                        execute_full_install_sequence(dry=dry, ad_max=ad_max, poll=poll)

                    same_q_count = 0
                    same_progress_count = 0
                    last_completed_progress = None
                    answered_sig = None
                    time.sleep(1.0)
                    continue

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

            # Bonus popup
            if bonus_btn:
                log(f"BONUS button '{bonus_btn.label or bonus_btn.rid}' at {bonus_btn.click}")
                if not dry and bonus_btn.click:
                    tap(*bonus_btn.click)
                    time.sleep(0.8)
                    handle_ad(None, dry=dry, max_seconds=ad_max, poll=poll)
                    time.sleep(1.0)
                    # Check progress after ad completion
                    post_nodes = dump_nodes()
                    new_progress = get_progress(post_nodes)
                    if new_progress:
                        if new_progress == last_completed_progress:
                            same_progress_count += 1
                            log(f"[QUIZ] Progress '{new_progress}' repeated after ad (count {same_progress_count}/3)")
                        else:
                            same_progress_count = 0
                            last_completed_progress = new_progress
                idle = 0
                time.sleep(ACTION_SETTLE)
                continue

            # Next / Submit
            nxt = find_button(nodes, NEXT_WORDS)
            if nxt and nxt.click:
                log(f"NEXT button '{nxt.label}' -> tap")
                if not dry:
                    tap(*nxt.click)
                idle = 0
                time.sleep(ACTION_SETTLE)
                continue

        # =================================================================== #
        # Screen Branch 3: WATCH VIDEO SCREEN (WatchAndEarnActivity)
        # =================================================================== #
        if is_watch_screen(nodes, focus_act):
            cur, tot, p_str = get_watch_progress(nodes)
            if is_watch_complete(nodes):
                log(f"[WATCH VIDEO COMPLETE] All videos completed ({p_str or '20/20'})! Tasks 100% finished.")
                break

            # Countdown timer in Watch Video
            timer = by_rid(nodes, "timerText")
            if not timer:
                for n in nodes:
                    if n.text and "wait" in n.text.lower() and "sec" in n.text.lower():
                        timer = n
                        break
            if timer and timer.text and "wait" in timer.text.lower():
                log(f"[WATCH VIDEO] Countdown: {timer.text}")
                time.sleep(1.0)
                continue

            # Check if Play Video button is present
            btn_watch = by_rid(nodes, "btn_watch_now")
            if btn_watch and btn_watch.click:
                if same_video_count >= 3:
                    log(f"[WATCH VIDEO] Progress '{p_str}' repeated 3 times -> INSTALL TASK DETECTED!")
                    log(f"[INSTALL TASK] 4th attempt: Tapping 'Play Video' at {btn_watch.click} to trigger Ad...")
                    if not dry:
                        tap(*btn_watch.click)
                        time.sleep(1.0)
                        execute_full_install_sequence(dry=dry, ad_max=ad_max, poll=poll)
                    same_video_count = 0
                    last_watch_completed_progress = None
                    time.sleep(ACTION_SETTLE)
                    continue

                log(f"[WATCH VIDEO] Tapping 'Play Video' (Progress: {p_str or '-'}) ...")
                if not dry:
                    tap(*btn_watch.click)
                    time.sleep(1.0)
                    handle_ad(None, dry=dry, max_seconds=ad_max, poll=poll)
                    time.sleep(1.0)
                    post_nodes = dump_nodes()
                    _, _, new_p_str = get_watch_progress(post_nodes)
                    if new_p_str:
                        if new_p_str == last_watch_completed_progress:
                            same_video_count += 1
                            log(f"[WATCH VIDEO] Progress '{new_p_str}' repeated after ad (count {same_video_count}/3)")
                        else:
                            same_video_count = 0
                            last_watch_completed_progress = new_p_str
                idle = 0
                time.sleep(ACTION_SETTLE)
                continue
                if not dry:
                    tap(*btn_watch.click)
                    time.sleep(1.0)
                    handle_ad(dump_nodes(), dry=dry, max_seconds=ad_max, poll=poll)
                idle = 0
                time.sleep(ACTION_SETTLE)
                continue

            # Intermediate claim / collect / OK dialogs
            nxt = find_button(nodes, NEXT_WORDS)
            if nxt and nxt.click:
                log(f"[WATCH VIDEO] Dialog button '{nxt.label}' -> tap")
                if not dry:
                    tap(*nxt.click)
                idle = 0
                time.sleep(ACTION_SETTLE)
                continue

        # =================================================================== #
        # Screen Branch 4: Any standard dialog / popup outside Home Screen
        # =================================================================== #
        nxt = find_button(nodes, NEXT_WORDS)
        if nxt and nxt.click and not is_home_screen(nodes, focus_act):
            log(f"POPUP button '{nxt.label}' -> tap")
            if not dry:
                tap(*nxt.click)
            idle = 0
            time.sleep(ACTION_SETTLE)
            continue

        idle += 1
        if idle in (25, 60, 120):
            log(f"Waiting... no actionable element ({idle} polls). phase={phase} "
                f"focus={focus_pkg}/{focus_act} labels={all_labels(nodes, 40)[:180]}")
            if idle == 120:
                screenshot(os.path.join(
                    BASE_DIR, f"stuck_{time.strftime('%H%M%S')}.png"))
        time.sleep(0.5)

    log("BOT stopped. All targeted tasks completed.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["all", "quiz", "video"], default="all",
                    help="Task to run: 'all' (quiz then watch video), 'quiz' only, or 'video' only")
    ap.add_argument("--max-steps", type=int, default=1000)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--poll", type=float, default=DEFAULT_POLL)
    ap.add_argument("--ad-max", type=int, default=AD_MAX_SECONDS)
    ap.add_argument("--serial", default="")
    ap.add_argument("--open", action="store_true", help="bring app to foreground")
    args = ap.parse_args()
    try:
        run(task=args.task, max_steps=args.max_steps, dry=args.dry_run, poll=args.poll,
            ad_max=args.ad_max, open_app=args.open)
    except KeyboardInterrupt:
        log("Interrupted by user.")
