#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NON-STOP FREE AI AUTONOMOUS BOT
Auto-play Free Fire Daily Gaming Quiz - Answer questions, claim bonus, handle ads.
Uses local Ollama (llama3.2:latest) for 100% free offline AI vision & quiz solving.
"""
import os
import sys
import time
import json
import re
import subprocess
import threading
import glob
import xml.etree.ElementTree as ET

# Import helper functions from text_ai_autobot and sound_notifier
from text_ai_autobot import (
    extract_quiz_info,
    warmup_ollama,
    ask_gemini_quiz,
    ask_ollama_quiz,
    resolve_option_click,
    smart_fallback_solve,
    detect_and_handle_common_dialogs,
    ask_ollama_general_event,
)
from sound_notifier import (
    register_exit_sound,
    notify_script_stopped,
    notify_error,
    prompt_task_complete,
)

# ============================================================
# AI Configuration
# ============================================================

def load_ai_config():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        cfg = {}
    cfg.setdefault("provider", "ollama")
    cfg.setdefault("gemini_api_key", "")
    cfg.setdefault("gemini_model", "gemini-3.8-flash")
    cfg.setdefault("ollama_host", "http://localhost:11434")
    cfg.setdefault("ollama_vision_model", "llama3.2-vision")
    cfg.setdefault("use_zero_token_mode_first", True)
    cfg.setdefault("max_loops", 999999)
    cfg.setdefault("loop_delay_seconds", 2.0)
    return cfg


AI_VISION_DECISION_PROMPT = """You are an autonomous AI Mobile Game & App Automation Agent.
Look at this mobile phone screen.
Decide what immediate action to perform to progress or finish the task.

Instructions:
1. If an 'AWESOME! Bonus Coins' popup is shown with an orange 'Add Bonus' button: return action='CLICK_ADD_BONUS'.
2. If a Quiz question with 4 options is shown: find the correct answer and return action='CLICK_OPTION', option='A' or 'B' or 'C' or 'D'.
3. If an ad or interstitial is shown: return action='CLOSE_AD'.
4. If a 'Wait ... sec' timer is shown: return action='WAIT'.
5. If 'Limit Over' or 'Task Completed' is shown: return action='DONE'.
6. If on the Home screen with 'Daily Gaming Quiz': return action='START_QUIZ'.
7. If on 'Watch Video' task screen with a 'Play Video' button: return action='PLAY_VIDEO'.

Respond STRICTLY in JSON format:
{
  "screen_summary": "<brief description of screen>",
  "task_counter": "<progress counter like '14/20' or '0/15' or null if not shown>",
  "action": "CLICK_OPTION" | "CLICK_ADD_BONUS" | "PLAY_VIDEO" | "CLOSE_AD" | "START_QUIZ" | "CLICK" | "BACK" | "WAIT" | "DONE",
  "option": "A" | "B" | "C" | "D" | null,
  "x": <integer x coordinate or null>,
  "y": <integer y coordinate or null>,
  "reason": "<why this action was chosen>",
  "is_task_finished": <true | false>
}
"""

# Global state
STATE = {
    "last_task_counter": "",
    "counter_seen_time": 0.0,
}
LAST_LIMIT_TIME = 0.0

QUIZ_STATE = {
    "last_quiz_id": None,
    "repeat_count": 0,
    "pending_uninstall_loops": 0,
    "target_app_package": "com.shake.master",
}

CONFIG = None

# APK and package constants
DUMMY_APK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
    "in.binarybox.blackscreen for ad installation.apk")
DUMMY_PACKAGE = "in.binarybox.blackscreen"
TARGET_APP = "com.shake.master"

# Auto-detect device serial
ADB_DEVICE = None
try:
    res = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10)
    for line in res.stdout.splitlines():
        line = line.strip()
        if "device" in line and "List" not in line:
            parts = line.split()
            if len(parts) >= 2 and "emulator-" not in parts[0]:
                ADB_DEVICE = parts[0]
                break
except Exception:
    pass


def get_adb():
    return "adb"


def get_devices():
    res = subprocess.run([get_adb(), "devices"], capture_output=True, text=True, timeout=10)
    out = res.stdout
    devices = []
    for line in out.splitlines():
        line = line.strip().replace("\r", "")
        if "List of" in line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[-1] == "device":
            d = parts[0]
            if d and not d.startswith("emulator-"):
                devices.append(d)
    return devices


def select_device(preferred=None):
    devices = get_devices()
    if preferred and preferred in devices:
        return preferred
    for d in devices:
        if d and not d.startswith("emulator-"):
            return d
    return devices[0] if devices else None


def run_adb(args):
    cmd = [get_adb()]
    if ADB_DEVICE:
        cmd += ["-s", ADB_DEVICE]
    cmd += list(args)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return res.stdout.replace("\r", "")
    except Exception as e:
        print(f"[ADB Error] {e}", flush=True)
        return None


def tap(x, y):
    print(f"  [TAP] Clicking on phone at ({x}, {y})", flush=True)
    run_adb(["shell", "input", "tap", str(x), str(y)])


def send_back():
    print("  [BACK] Pressing Android Back button", flush=True)
    run_adb(["shell", "input", "keyevent", "4"])


def get_current_app_package():
    """Get the currently focused app package name."""
    try:
        res = subprocess.run(
            [get_adb(), "shell", "dumpsys", "window"],
            capture_output=True, text=True, timeout=10)
        for line in res.stdout.splitlines():
            if "mCurrentFocus" in line:
                m = re.search(r"u0\s+([a-zA-Z0-9_.]+)", line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None


def capture_mobile_screenshot(save_path):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(script_dir, save_path)
    run_adb(["shell", "screencap", "-p", "/sdcard/screen.png"])
    run_adb(["pull", "/sdcard/screen.png", full_path])
    return full_path


def extract_task_counter(elements):
    """Extracts task counter like '9/20' from screen elements."""
    for i, el in enumerate(elements):
        t = (el.get("text") or "").strip()
        m = re.search(r"(\d+)\s*/\s*(\d+)", t)
        if m:
            return f"{m.group(1)}/{m.group(2)}"
        m = re.match(r"^(\d+)\s*/$", t)
        if m and i + 1 < len(elements):
            next_t = (elements[i+1].get("text") or "").strip()
            m2 = re.match(r"^/\s*(\d+)$", next_t)
            if m2:
                return f"{m.group(1)}/{m2.group(1)}"
        m = re.match(r"^/\s*(\d+)$", t)
        if m and i > 0:
            prev_t = (elements[i-1].get("text") or "").strip()
            m1 = re.match(r"^(\d+)\s*/$", prev_t)
            if m1:
                return f"{m1.group(1)}/{m.group(1)}"
    return None


def check_pending_uninstall():
    """Checks if background deletion of in.binarybox is due on the 2nd loop."""
    loops = QUIZ_STATE.get("pending_uninstall_loops", 0)
    if loops and loops > 0:
        print(f"  [INSTALL BYPASS] Countdown to background uninstall: {loops} loop(s) remaining.", flush=True)
        QUIZ_STATE["pending_uninstall_loops"] = loops - 1
        if loops <= 1:
            print("  [BACKGROUND] Deleting/Uninstalling in.binarybox.blackscreen in background...", flush=True)
            res = run_adb(["uninstall", DUMMY_PACKAGE])
            if res and "Success" in res:
                print("  [BACKGROUND] Finished removing in.binarybox (Success). Tasks continue seamlessly!", flush=True)
            else:
                print(f"  [BACKGROUND] Uninstall result: {res}", flush=True)
            QUIZ_STATE["pending_uninstall_loops"] = None
            return True
    return False


def alert_user_on_laptop_and_mobile(reason):
    """Alerts user on Laptop and Mobile Phone when manual intervention is needed."""
    print("\n  ===================================================", flush=True)
    print("  [ATTENTION NEEDED] MANUAL INTERVENTION REQUIRED!", flush=True)
    print(f"  Reason: {reason}", flush=True)
    print("  Triggering alert on Mobile Phone & Laptop...", flush=True)
    print("  ===================================================\n", flush=True)
    try:
        play_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sound_notifier.py")
        if os.path.exists(play_script):
            subprocess.Popen([sys.executable, play_script, "alert"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    try:
        import winsound
        for _ in range(3):
            winsound.Beep(1200, 350)
            time.sleep(0.1)
        winsound.Beep(1200, 350)
    except Exception:
        print("  ", flush=True)


def compress_image_for_ai(img_path, target_width):
    out_path = img_path.rsplit(".", 1)[0] + "_ai.jpg"
    abs_in = os.path.abspath(img_path)
    abs_out = os.path.abspath(out_path)
    try:
        import PIL.Image
        img = PIL.Image.open(abs_in)
        img = img.convert("RGB")
        orig_w, orig_h = img.size
        scale = target_width / orig_w
        target_height = int(orig_h * scale)
        resized = img.resize((target_width, target_height), PIL.Image.LANCZOS)
        resized.save(abs_out, "JPEG", quality=85)
        return abs_out, orig_w, orig_h
    except Exception:
        pass
    # Fallback: use powershell
    ps_cmd = (
        "Add-Type -AssemblyName System.Drawing;"
        f"$src = [System.Drawing.Image]::FromFile('{abs_in}');"
        "$ow = $src.Width; $oh = $src.Height;"
        f"$tw = {target_width};"
        "$th = [int]($oh * ($tw / $ow));"
        "$dst = New-Object System.Drawing.Bitmap $tw, $th;"
        "$gr = [System.Drawing.Graphics]::FromImage($dst);"
        "$gr.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic;"
        "$gr.DrawImage($src, 0, 0, $tw, $th);"
        f"$dst.Save('{abs_out}', [System.Drawing.Imaging.ImageFormat]::Jpeg);"
        "$gr.Dispose(); $dst.Dispose(); $src.Dispose();"
        "$ow,$oh,$tw,$th"
    )
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd],
                             capture_output=True, text=True, timeout=30)
        parts = res.stdout.strip().split(",")
        if len(parts) == 4:
            return abs_out, int(parts[0]), int(parts[1])
    except Exception:
        pass
    return img_path, 1080, 2400


def get_ui_elements():
    """Parse uiautomator XML dump into list of element dicts."""
    run_adb(["shell", "uiautomator", "dump", "/sdcard/ui.xml"])
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ui_path = os.path.join(script_dir, "_ui.xml")
    res = subprocess.run([get_adb(), "pull", "/sdcard/ui.xml", ui_path],
                         capture_output=True, text=True)
    try:
        with open(ui_path, "r", encoding="utf-8") as f:
            xml_content = f.read()
    except Exception:
        return []
    try:
        root = ET.fromstring(xml_content)
    except Exception:
        return []
    elements = []
    for node in root.iter():
        text = (node.get("{http://schemas.android.com/apk/res/android}text") or "").strip()
        desc = (node.get("{http://schemas.android.com/apk/res/android}content-desc") or "").strip()
        bounds_str = node.get("{http://schemas.android.com/apk/res/android}bounds") or ""
        clickable = node.get("clickable")
        cx, cy = None, None
        m = re.search(r"\[(\d+),(\d+)\]\s*\[(\d+),(\d+)\]", bounds_str)
        if m:
            x1, y1, x2, y2 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
        elements.append({
            "text": text,
            "desc": desc,
            "bounds": bounds_str,
            "clickable": clickable == "true" if clickable else None,
            "cx": cx,
            "cy": cy,
        })
    return elements


def call_gemini_vision(img_path, prompt, config):
    """Free Tier Gemini Vision via Google AI Studio API key."""
    api_key = config.get("gemini_api_key", "")
    if not api_key:
        return None
    model = config.get("gemini_model", "gemini-3.8-flash")
    comp_path, orig_w, orig_h = compress_image_for_ai(img_path, 1080)
    try:
        import base64
        with open(comp_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None
    cur_prompt = prompt + f"\nNote: Image dimensions are {orig_w}x{orig_h}. Return x, y coordinates based on this image dimensions."
    payload = {
        "contents": [{
            "parts": [
                {"text": cur_prompt},
                {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}
            ]
        }],
        "generationConfig": {"temperature": 0.1}

    }
    data_bytes = json.dumps(payload).encode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    try:
        # Write payload to temp file to avoid Windows command-line length limit
        import tempfile as _tmp
        _fd, _path = _tmp.mkstemp(suffix=".json", prefix="gemini_payload_")
        try:
            with open(_fd, "wb") as _f:
                _f.write(data_bytes)
            req = subprocess.run(
                ["curl", "-s", "-X", "POST", url,
                 "-H", "Content-Type: application/json",
                 "--data-binary", "@" + _path],
                capture_output=True, text=True, timeout=120)
            resp = req.stdout
        finally:
            try:
                os.unlink(_path)
            except Exception:
                pass
        data = json.loads(resp)
        ans_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if ans_text:
            try:
                return json.loads(ans_text)
            except Exception:
                return {"raw": ans_text}
        return None
    except Exception as e:
        print(f"  [Gemini Vision Error] {e}", flush=True)
        return None


def call_ollama_vision(img_path, prompt, config):
    """100% Free & Offline Local Ollama Vision Model."""
    host = config.get("ollama_host", "http://localhost:11434")
    model = config.get("ollama_vision_model", "llama3.2-vision")
    comp_path, orig_w, orig_h = compress_image_for_ai(img_path, 1080)
    try:
        import base64
        with open(comp_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return {}
    cur_prompt = prompt + f"\nNote: Image dimensions are {orig_w}x{orig_h}. Return x, y coordinates based on this image dimensions."
    payload = {
        "model": model,
        "prompt": cur_prompt,
        "images": [img_b64],
        "format": "json",
        "stream": False,
        "keep_alive": "5m"
    }
    url = f"{host}/api/generate"
    try:
        # Write payload to temp file to avoid Windows command-line length limit (WinError 206)
        payload_bytes = json.dumps(payload).encode("utf-8")
        import tempfile
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="ollama_payload_")
        try:
            with open(tmp_fd, "wb") as tmp_f:
                tmp_f.write(payload_bytes)
            req = subprocess.run(
                ["curl", "-s", "-X", "POST", url,
                 "-H", "Content-Type: application/json",
                 "--data-binary", "@" + tmp_path],
                capture_output=True, text=True, timeout=120)
            resp = json.loads(req.stdout)
            res_text = resp.get("response", "{}")
            try:
                return json.loads(res_text)
            except Exception:
                return {"raw": res_text}
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except Exception as e:
        print(f"  [Ollama Vision Error] {e}", flush=True)
        return {}


def perform_fake_install_bypass():
    """
    Bypasses mandatory app installation tasks when a quiz repeats 3 times:
    1. Goes to Home screen
    2. Installs in.binarybox APK via ADB
    3. Opens it for 5 seconds
    4. Switches back to our app
    5. Clicks 'Add Bonus' if present
    6. Schedules background deletion on 2nd loop.
    """
    print("\n====================================================", flush=True)
    print(" [INSTALL BYPASS] Triggered: Bypassing Ad Installation!", flush=True)
    print("====================================================", flush=True)

    app_pkg = get_current_app_package()
    if app_pkg:
        QUIZ_STATE["target_app_package"] = app_pkg
    target_app = QUIZ_STATE.get("target_app_package", "com.shake.master")

    # Step 1: Go to Home screen
    print(" [STEP 1] Going to phone Home Screen...", flush=True)
    run_adb(["shell", "input", "keyevent", "3"])
    time.sleep(1.5)

    # Step 2: Install APK
    print(f" [STEP 2] Installing '{os.path.basename(DUMMY_APK_PATH)}'...", flush=True)
    if os.path.exists(DUMMY_APK_PATH):
        run_adb(["uninstall", DUMMY_PACKAGE])
        res = run_adb(["install", "-r", "-g", DUMMY_APK_PATH])
        print(f"   Install Status: {res}", flush=True)
    else:
        print(f"?? APK not found at: {DUMMY_APK_PATH}", flush=True)

    # Step 3: Open dummy app for 5 seconds
    print(f" [STEP 3] Opening {DUMMY_PACKAGE} for 5 seconds...", flush=True)
    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])
    time.sleep(5)

    # [VERIFY] Check we are in dummy app (not Play Store)
    _op_pkg = get_current_app_package()
    if _op_pkg and _op_pkg != DUMMY_PACKAGE:
        print(f"? [BYPASS VERIFY] Open returned to '{_op_pkg}' not dummy. Dismissing...", flush=True)
        for _vbi in range(5):
            run_adb(["shell", "input", "keyevent", "4"])
            time.sleep(0.4)
            _vcp = get_current_app_package()
            if _vcp == DUMMY_PACKAGE:
                print(f"? [BYPASS VERIFY] Reached dummy after {_vbi+1} back presses.", flush=True)
                break
            if _vcp == target_app:
                print("? [BYPASS VERIFY] Already back in target app.", flush=True)
                break

    # Step 4: Return to our app
    print(f" [STEP 4] Switching back to our app ({target_app})...", flush=True)
    run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])
    time.sleep(2.5)

    # [VERIFY] Confirm we are back in target app
    _back_pkg = get_current_app_package()
    if _back_pkg != target_app:
        err_info = f"got '{_back_pkg}' not '{target_app}'"
        print(f"? [BYPASS VERIFY] Return failed ({err_info}). Force-launching...", flush=True)
        for _fi in range(5):
            run_adb(["shell", "input", "keyevent", "3"])
            time.sleep(0.5)
            run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])
            time.sleep(3.0)
            _bp = get_current_app_package()
            if _bp == target_app:
                print(f"? [BYPASS VERIFY] Force-launch OK on attempt {_fi+1}.", flush=True)
                break

    # Step 5: Check screen for Add Bonus or close dialog
    print(" [STEP 5] Checking screen after returning to app...", flush=True)
    elements = get_ui_elements()
    clicked_action = False

    for e in elements:
        et = (e.get("text") or "")
        t = et.strip().lower()
        if "add bonus" in t or t == "add" or "claim" in t or "collect" in t:
            eb = e.get("bounds", {})
            cx = eb.get("cx", 0)
            cy = eb.get("cy", 0)
            print(f"  Found '{et}' button -> Tapping ({cx}, {cy})", flush=True)
            tap(cx, cy)
            clicked_action = True
            time.sleep(1.5)
            break

    if not clicked_action:
        for e in elements:
            et = (e.get("text") or "")
            t = et.strip().lower()
            clickable = e.get("clickable")
            if t in ["close", "skip", "dismiss", "ok", "cancel"] or (clickable and "close" in t):
                eb = e.get("bounds", {})
                cx = eb.get("cx", 0)
                cy = eb.get("cy", 0)
                print(f"  Found dialog '{et}' -> Tapping ({cx}, {cy})", flush=True)
                tap(cx, cy)
                clicked_action = True
                time.sleep(1)
                break

    if not clicked_action:
        print("  No 'Add Bonus' popup detected. Continuing to main loop.", flush=True)
    time.sleep(1)

    # Step 6: Schedule background deletion
    QUIZ_STATE["pending_uninstall_loops"] = 2
    QUIZ_STATE["repeat_count"] = 0
    QUIZ_STATE["last_quiz_id"] = None
    print(" [STEP 6] Scheduled in.binarybox deletion in 2nd loop (background).", flush=True)
    print(" [INSTALL BYPASS COMPLETE] Continuing bot task!\n", flush=True)
    return True


def dismiss_ad_if_present():
    """Dismiss ad close button or tap top-right corner."""
    elements = get_ui_elements()
    for e in elements:
        et = (e.get("text") or "")
        t = et.strip().lower()
        clickable = e.get("clickable")
        if t in ["close", "close ad", "skip", "dismiss"] or (clickable and "close" in t):
            eb = e.get("bounds", {})
            cx = eb.get("cx", 0)
            cy = eb.get("cy", 0)
            print(f"  Found close '{et}' -> Tapping ({cx}, {cy})", flush=True)
            tap(cx, cy)
            return True
    print("  Tapping top-right ad cross area (1013, 176)...", flush=True)
    tap(1013, 176)
    return False


def handle_add_bonus_and_wait():
    """
    Quiz completion flow:
    1. Tap 'Add Bonus' button
    2. Check for install task BEFORE dismissing ad
    3. If found: run install bypass (install -> open -> close -> return)
    4. Then dismiss ad overlay
    5. Verify counter advanced
    """
    prev_counter = STATE.get("last_task_counter", "")
    print(f"\n  [BONUS] Tapping 'Add Bonus' for Task '{prev_counter}'...", flush=True)

    # 1. Tap Add Bonus
    elements = get_ui_elements()
    tapped = False
    for e in elements:
        et = (e.get("text") or "")
        t = et.strip().lower()
        if "add bonus" in t or t == "add":
            eb = e.get("bounds", {})
            cx = eb.get("cx", 0)
            cy = eb.get("cy", 0)
            print(f"  Found '{et}' -> Tapping ({cx}, {cy})", flush=True)
            tap(cx, cy)
            tapped = True
            break
    if not tapped:
        print("  Tapping 'Add Bonus' default (500, 1705)...", flush=True)
        tap(500, 1705)

    # 2. Check for install task BEFORE dismissing ad
    print("\n  [AD CHECK] Checking for install task before closing ad...", flush=True)
    ad_elements = get_ui_elements()
    install_task_found = False
    for ad_e in ad_elements:
        ad_t = (ad_e.get("text") or "").strip().lower()
        if any(kw in ad_t for kw in ["play video", "final watch", "watch to unlock",
                                        "watch video", "install", "open app"]):
            print(f"  [INSTALL TASK] Detected '{ad_t}' -> Running install bypass BEFORE closing ad...", flush=True)
            perform_fake_install_bypass()
            install_task_found = True
            break
    if not install_task_found:
        print("  [AD FINISHED] No install task - dismissing ad overlay...", flush=True)
        dismiss_ad_if_present()
    time.sleep(2)

    # 3. Read screen: check if counter advanced
    new_elements = get_ui_elements()
    new_counter = extract_task_counter(new_elements)

    if new_counter:
        info = f"Task counter after 25s cycle: '{new_counter}' (Before: '{prev_counter}')"
        print(f"  [SCREEN READ] {info}", flush=True)
        if prev_counter and new_counter == prev_counter:
            if QUIZ_STATE["last_quiz_id"] == new_counter:
                QUIZ_STATE["repeat_count"] += 1
            else:
                QUIZ_STATE["last_quiz_id"] = new_counter
                QUIZ_STATE["repeat_count"] = 1
            info2 = f"Task counter '{new_counter}' repeated ({QUIZ_STATE['repeat_count']}/3 loops)"
            print(f"  [QUIZ REPEAT] {info2}", flush=True)
            if QUIZ_STATE["repeat_count"] >= 3:
                print(f"\n  [TRIGGER BYPASS] '{new_counter}' repeated 3 times!", flush=True)
                perform_fake_install_bypass()
                QUIZ_STATE["last_quiz_id"] = None
                QUIZ_STATE["repeat_count"] = 0
                return False, "INSTALL_BYPASS_EXECUTED"
            info3 = f"Counter '{new_counter}' seen {QUIZ_STATE['repeat_count']}/3 times. Continuing..."
            print(f"  [INFO] {info3}", flush=True)
        else:
            print(f"\n  [PROGRESS] Advanced from '{prev_counter}' -> '{new_counter}'! Task completed.\n", flush=True)
            STATE["last_task_counter"] = new_counter
            STATE["counter_seen_time"] = time.time()
    else:
        print("  [INFO] Screen changed or ad dismissed. Returning to main loop.\n", flush=True)

    return False, "COMPLETED_QUIZ_CYCLE"




def handle_play_video_and_wait(cx=540, cy=1760):
    """
    Executes the user's Watch Video task flow:
    1. Click 'Play Video' button
    2. Wait 25 seconds for the video ad to finish
    3. Dismiss ad overlay
    4. Check for and claim any 'Add Bonus' / 'Claim' popup
    5. Read screen and verify task progress; alert if task counter repeated
    """
    elements = get_ui_elements()
    for e in elements:
        t = e.get("text", "").strip().lower()
        if "final watch" in t:
            print(f"�   [FINAL WATCH] Found '{e['text']}' -> Tapping ({e['bounds']['cx']}, {e['bounds']['cy']})", flush=True)
            tap(e['bounds']['cx'], e['bounds']['cy'])
            print("�  [FINAL WATCH] Waiting 5 seconds before going to Home screen...", flush=True)
            time.sleep(5)
            print("�   [FINAL WATCH BYPASS] Proceeding to install in.binarybox application...", flush=True)
            perform_fake_install_bypass()
            return False, "FINAL_WATCH_BYPASS"

    prev_counter = extract_task_counter(elements) or STATE.get("last_task_counter", "")
    if prev_counter:
        STATE["last_task_counter"] = prev_counter

    print(f"\n�   [WATCH VIDEO] Clicking 'Play Video' at ({cx}, {cy}) for Task '{prev_counter}'...", flush=True)
    tap(cx, cy)
    
    # Video ad wait removed by user request - proceed immediately
    print("\n�  [VIDEO AD CYCLE] Video started! Checking screen immediately without ad wait...", flush=True)
    time.sleep(1)
        
    time.sleep(2)
    # Dismiss any ad 'X' or close button
    print("�   [VIDEO FINISHED] Dismissing video ad overlay...", flush=True)
    dismiss_ad_if_present()
    time.sleep(2)
    
    # Check if 'Add Bonus' or 'Claim' popup appeared after video
    elements = get_ui_elements()
    for e in elements:
        t = e.get("text", "").strip().lower()
        if "add bonus" in t or t == "add" or "claim" in t:
            print(f"�   Found post-video bonus '{e['text']}' -> Tapping ({e['bounds']['cx']}, {e['bounds']['cy']})", flush=True)
            tap(e['bounds']['cx'], e['bounds']['cy'])
            time.sleep(2)
            break
            
    # Read screen again to update counter
    new_elements = get_ui_elements()
    new_counter = extract_task_counter(new_elements)
    if new_counter:
        print(f"�   [SCREEN READ] Video counter after 25s: '{new_counter}' (Before: '{prev_counter}')", flush=True)
        if prev_counter and new_counter == prev_counter:
            if QUIZ_STATE["last_quiz_id"] == new_counter:
                QUIZ_STATE["repeat_count"] += 1
            else:
                QUIZ_STATE["last_quiz_id"] = new_counter
                QUIZ_STATE["repeat_count"] = 1
            print(f"�   [QUIZ REPEAT] Video task counter '{new_counter}' repeated ({QUIZ_STATE['repeat_count']}/3 loops)", flush=True)
            if QUIZ_STATE["repeat_count"] >= 3:
                print(f"�   [TRIGGER BYPASS] Task counter '{new_counter}' repeated 3 times in 3 loops!", flush=True)
                perform_fake_install_bypass()
                return False, "INSTALL_BYPASS_EXECUTED"
            print(f"� �  Video task counter '{new_counter}' seen {QUIZ_STATE['repeat_count']}/3 times. Continuing bot task...", flush=True)
        else:
            print(f"�   [VIDEO PROGRESS] Progressed from '{prev_counter}' -> '{new_counter}'!\n", flush=True)
            STATE["last_task_counter"] = new_counter
            STATE["counter_seen_time"] = time.time()
    else:
        print("� �  Screen changed or ad dismissed. Returning to main decision loop.\n", flush=True)
            
    return False, "PLAY_VIDEO_CYCLE"

def execute_smart_action(decision):
    action = decision.get("action", "").upper()
    reason = decision.get("reason", "")
    summary = decision.get("screen_summary", "")

    # 1. Option Letter mapping (100% precision pixel alignment on phone)
    FIXED_OPTIONS = {
        "A": (540, 1328),
        "B": (540, 1502),
        "C": (540, 1676),
        "D": (540, 1850)
    }
    
    opt = decision.get("option") or decision.get("selected_option") or decision.get("correct_option")
    if not opt:
        # Check if option letter was mentioned in reason or action
        for k in ["A", "B", "C", "D"]:
            if f"option {k.lower()}" in reason.lower() or f"'{k.lower()}'" in reason.lower() or f"option {k}" in reason or f"({k.lower()})" in reason.lower():
                opt = k
                break

    if opt and opt.upper() in FIXED_OPTIONS:
        target_opt = opt.upper()
        coords = FIXED_OPTIONS.get(target_opt, (540, 1328))
        print(f"�   [QUIZ ANSWER] Selected Option {target_opt} -> Tapping at exact pixel {coords}", flush=True)
        tap(coords[0], coords[1])
        return False, "CLICK_OPTION"

    # 2. Add Bonus button -> Triggers the full 25s wait & screen verification flow!
    if action == "CLICK_ADD_BONUS" or "add bonus" in reason.lower():
        return handle_add_bonus_and_wait()

    # 2.3 Final Watch button -> First click Final Watch, then goto home screen and install
    if action == "FINAL_WATCH" or "final watch" in reason.lower():
        x = decision.get("x") or 540
        y = decision.get("y") or 2178
        print(f"�   [FINAL WATCH] Tapping Final Watch button at ({x}, {y})...", flush=True)
        tap(x, y)
        print("�  [FINAL WATCH] Waiting 5 seconds before going to Home screen...", flush=True)
        time.sleep(5)
        print("�   [FINAL WATCH BYPASS] Proceeding to install in.binarybox application...", flush=True)
        perform_fake_install_bypass()
        return False, "FINAL_WATCH_BYPASS"

    # 2.5 Play Video button -> Triggers the full 25s video wait & progress flow!
    if action == "PLAY_VIDEO" or "play video" in reason.lower():
        x = decision.get("x") or 540
        y = decision.get("y") or 1760
        return handle_play_video_and_wait(x, y)

    # 3. Close Ad
    if action == "CLOSE_AD" or "close ad" in reason.lower():
        print("�  [CLOSE AD] Tapping top-right close area / pressing Back", flush=True)
        tap(1013, 176)
        time.sleep(1)
        send_back()
        return

    # 4. Start Quiz banner on Home
    if action == "START_QUIZ" or "daily gaming quiz" in reason.lower():
        print("�   [START QUIZ] Tapping Daily Gaming Quiz banner at (540, 550)", flush=True)
        tap(540, 550)
        return

    # 5. Lock screen unlock
    if "lock" in summary.lower() or "always-on" in summary.lower():
        print("�   [UNLOCK] Swiping up to unlock phone screen...", flush=True)
        run_adb(["shell", "input", "swipe", "540", "1900", "540", "500", "250"])
        time.sleep(1)
        return

    # 6. Generic Click with coordinate boundary & scaling verification
    if action == "CLICK":
        x = decision.get("x")
        y = decision.get("y")
        if x and y:
            # If coordinates are over screen bounds, fix scaling
            if y > 2400:
                y = int(y / 2)
            if x > 1080:
                x = int(x / 2)
            # Clamp to safe screen area
            x = max(50, min(1030, x))
            y = max(50, min(2350, y))
            tap(x, y)
    elif action == "BACK":
        send_back()
    elif action == "WAIT":
        time.sleep(3)

def decide_and_execute_step(config):
    # Step 1: Capture latest mobile screen
    img_path = capture_mobile_screenshot("mobile_screen.png")
    elements = get_ui_elements()
    all_text = " ".join([e["text"].lower() for e in elements])
    
    # [STAY-IN-APP GUARD] If we left the quiz app (Play Store, Home, etc.), force return.
    _cur_pkg = get_current_app_package()
    _tgt_pkg = QUIZ_STATE.get("target_app_package") or "com.shake.master"
    if _cur_pkg and _cur_pkg != _tgt_pkg:
        msg = "\n??? [STAY-IN-APP] Currently in '" + str(_cur_pkg) + "' (target: '" + str(_tgt_pkg) + "'). Forcing return to quiz app..."
        print(msg, flush=True)
        for _bi in range(8):
            run_adb(["shell", "input", "keyevent", "4"])
            time.sleep(0.4)
            _cp = get_current_app_package()
            if _cp == _tgt_pkg:
                print("??? [STAY-IN-APP] Returned after " + str(_bi+1) + " back presses.", flush=True)
                break
        _cp2 = get_current_app_package()
        if _cp2 != _tgt_pkg:
            print("??? [STAY-IN-APP] Still not in target ('" + str(_cp2) + "'). Home + launch...", flush=True)
            run_adb(["shell", "input", "keyevent", "3"])
            time.sleep(1.0)
            run_adb(["shell", "monkey", "-p", _tgt_pkg, "-c", "android.intent.category.LAUNCHER", "1"])
            time.sleep(3.0)
            _cp3 = get_current_app_package()
            if _cp3 == _tgt_pkg:
                print("??? [STAY-IN-APP] Launched target app.", flush=True)
            else:
                print("??? [STAY-IN-APP] WARNING: still not in target ('" + str(_cp3) + "'). Retrying...", flush=True)
                for _ri in range(3):
                    run_adb(["shell", "input", "keyevent", "3"])
                    time.sleep(0.5)
                    run_adb(["shell", "monkey", "-p", _tgt_pkg, "-c", "android.intent.category.LAUNCHER", "1"])
                    time.sleep(3.0)
                    _cp4 = get_current_app_package()
                    if _cp4 == _tgt_pkg:
                        print("??? [STAY-IN-APP] Retry " + str(_ri+1) + ": Returned to target.", flush=True)
                        break
        elements = get_ui_elements()
        all_text = " ".join([e["text"].lower() for e in elements])


    # Check Done / Limit Over
    if "limit over" in all_text or "daily limit" in all_text or "task completed" in all_text:
        global LAST_LIMIT_TIME
        if time.time() - LAST_LIMIT_TIME > 30:
            print("�   [COMPLETED] Daily Limit Reached / Task complete for current task.", flush=True)
            return True, "DONE"
        else:
            # During cooldown after user chose Continue, skip triggering DONE
            pass

    # Step 2: Track task counter & 3-loop repeat detection (e.g. 9/20 stuck)
    counter = extract_task_counter(elements)
    question, options = extract_quiz_info(elements)
    quiz_key = counter if counter else question
    if quiz_key and ((question and options and len(options) >= 2) or counter):
        if QUIZ_STATE["last_quiz_id"] == quiz_key:
            QUIZ_STATE["repeat_count"] += 1
            print(f"�   [QUIZ REPEAT] Task '{quiz_key}' repeated ({QUIZ_STATE['repeat_count']}/3 loops)", flush=True)
        else:
            QUIZ_STATE["last_quiz_id"] = quiz_key
            QUIZ_STATE["repeat_count"] = 1
            print(f"�   [QUIZ TASK] Active Quiz task: '{quiz_key}' (Loop 1/3)", flush=True)

        if QUIZ_STATE["repeat_count"] >= 3:
            print(f"\n�   [TRIGGER BYPASS] Quiz task '{quiz_key}' repeated 3 times in 3 loops!", flush=True)
            perform_fake_install_bypass()
            return False, "INSTALL_BYPASS_EXECUTED"

    # Step 3: Zero-Token Quick Fast Path (0 API tokens consumed!)
    if config.get("use_zero_token_mode_first", True):
        # Check Add Bonus button FIRST -> Executes the full 25s wait & screen verification flow!
        for e in elements:
            t = e["text"].strip().lower()
            if "add bonus" in t or t == "add":
                return handle_add_bonus_and_wait()

        # Check Popup Dialogs (Connection reset, error, alert, etc.)
        if detect_and_handle_common_dialogs(elements):
            return False, "DIALOG_RESOLVED"

        # Check 'Final Watch' button -> First click Final Watch, then goto home screen and install
        for e in elements:
            t = e["text"].strip().lower()
            if "final watch" in t:
                print(f"�   [FINAL WATCH] Found '{e['text']}' button -> Tapping ({e['bounds']['cx']}, {e['bounds']['cy']})", flush=True)
                tap(e['bounds']['cx'], e['bounds']['cy'])
                print("�  [FINAL WATCH] Waiting 5 seconds before going to Home screen...", flush=True)
                time.sleep(5)
                print("�   [FINAL WATCH BYPASS] Proceeding to install in.binarybox application...", flush=True)
                perform_fake_install_bypass()
                return False, "FINAL_WATCH_BYPASS"

        # Check 'Play Video' button -> Executes the full 25s video wait & progress flow!
        for e in elements:
            t = e["text"].strip().lower()
            if "play video" in t or t == "play":
                return handle_play_video_and_wait(e["bounds"]["cx"], e["bounds"]["cy"])

        # Check Close Ad
        for e in elements:
            t = e["text"].strip().lower()
            if t in ["close", "close ad", "skip", "dismiss"] or (e.get("clickable") and "close" in t):
                print(f"�  [ZERO-TOKEN FAST] Found Close Button -> Tapping ({e['bounds']['cx']}, {e['bounds']['cy']})", flush=True)
                tap(e['bounds']['cx'], e['bounds']['cy'])
                return False, "CLICK_CLOSE_AD"
                
        # Check Timer
        for e in elements:
            t = e["text"].strip().lower()
            if "wait" in t and "sec" in t:
                print(f"�  [ZERO-TOKEN FAST] Waiting for timer: '{e['text']}'", flush=True)
                time.sleep(3)
                return False, "WAIT_TIMER"

        # Check Quiz Screen directly from UI elements (100% accurate Ollama quiz solver)
        question, options = extract_quiz_info(elements)
        if question and options and len(options) >= 2:
            print(f"\n�  [QUIZ DETECTED] Question: '{question}'", flush=True)
            opts_summary = ", ".join([f"{k}: '{v['text']}'" for k, v in sorted(options.items())])
            print(f"�   Options: {opts_summary}", flush=True)
            
            # Query Ollama
            print(f"�   Asking local Ollama ({config.get('ollama_model', 'llama3.2:latest')})...", flush=True)
            decision = ask_ollama_quiz(question, options, config)
            print(f"�   Ollama Decision: {decision}", flush=True)
            
            lbl, cx, cy, reason = resolve_option_click(decision, options)
            if not lbl:
                if config.get("gemini_api_key"):
                    print("�   Ollama timed out. Trying Gemini Cloud AI fallback...", flush=True)
                    gem_decision = ask_gemini_quiz(question, options, config)
                    if gem_decision:
                        lbl, cx, cy, reason = resolve_option_click(gem_decision, options)
                        if lbl:
                            print(f"�   Gemini Raw Decision: {gem_decision}", flush=True)
            if not lbl:
                print("�  Using Smart Gaming Rules fallback...", flush=True)
                lbl, cx, cy, reason = smart_fallback_solve(question, options)
                
            if lbl and cx and cy:
                print(f"�   [QUIZ ANSWER] Selected Option {lbl} ('{options[lbl]['text']}') -> Tapping exact pixel ({cx}, {cy})", flush=True)
                print(f"�   Reason: {reason}", flush=True)
                tap(cx, cy)
                time.sleep(2.0)
                return False, "CLICK_OPTION"
            else:
                print("� �  Could not confidently resolve correct option from quiz.", flush=True)

        # Check Autonomous Ollama Screen & Event Analyzer (Handles unknown popups, connection resets, dialogs)
        ollama_decision, candidates = ask_ollama_general_event(elements, config)
        if ollama_decision and ollama_decision.get("action") == "CLICK":
            target_idx = ollama_decision.get("target_index")
            target_text = str(ollama_decision.get("target_text") or "").strip().lower()
            reason = ollama_decision.get("reason", "")
            click_x, click_y = None, None
            if target_idx and isinstance(target_idx, int) and 1 <= target_idx <= len(candidates):
                c = candidates[target_idx - 1]
                click_x, click_y = c["cx"], c["cy"]
            elif target_text:
                for el in elements:
                    t = (el.get("text") or "").strip().lower()
                    if t and (target_text == t or target_text in t):
                        click_x = el.get("cx") if "cx" in el else el.get("bounds", {}).get("cx")
                        click_y = el.get("cy") if "cy" in el else el.get("bounds", {}).get("cy")
                        break
            # [SAFE CLICK] Only tap within safe screen bounds (avoid Play Store/Chrome redirects)
            if 50 <= click_x <= 1030 and 200 <= click_y <= 2200:
                print(f"  [OLLAMA ACTION] Resolved event popup -> Tapping ({click_x}, {click_y}) | Reason: {reason}", flush=True)
                tap(click_x, click_y)
                time.sleep(2)
                return False, "OLLAMA_EVENT_CLICK"
            else:
                print(f"  [SAFE CLICK] AI suggested out-of-bounds ({click_x}, {click_y}) - skipping to avoid wrong app.", flush=True)
                return False, "OLLAMA_SKIPPED_UNSAFE"
        elif ollama_decision and ollama_decision.get("action") == "BACK":
            print(f"�   [OLLAMA ACTION] Pressing Back | Reason: {ollama_decision.get('reason')}", flush=True)
            send_back()
            time.sleep(1.5)
            return False, "OLLAMA_EVENT_BACK"
    
    # Step 4: AI Vision Model Decision (Free Gemini or Local Ollama)
    provider = config.get("provider", "ollama")
    print(f"\n�   [AI VISION] Invoking Free Vision Engine ({provider})...", flush=True)
    
    decision = None
    try:
        if provider == "gemini_free":
            decision = call_gemini_vision(img_path, AI_VISION_DECISION_PROMPT, config)
        elif provider in ("ollama", "ollama_local"):
            decision = call_ollama_vision(img_path, AI_VISION_DECISION_PROMPT, config)
            if not decision:
                print("  [AI VISION] Ollama returned no result, falling back to Gemini Cloud AI...", flush=True)
                decision = call_gemini_vision(img_path, AI_VISION_DECISION_PROMPT, config)
        else:
            decision = call_gemini_vision(img_path, AI_VISION_DECISION_PROMPT, config)
    except Exception as e:
        print(f"� �  [AI Vision Fallback] {e}", flush=True)

    if not decision:
        print("� �  No AI decision made. Waiting 2 seconds...", flush=True)
        time.sleep(2)
        return False, "RETRY"
        
    summary = decision.get("screen_summary", "")
    action = decision.get("action", "").upper()
    print(f"�  �   [AI SAW]: {summary}", flush=True)
    print(f"�   [DECISION]: {action} -> {decision.get('reason')}", flush=True)

    if decision.get("is_task_finished") or action == "DONE":
        print("�   [AI BOT FINISHED] Task completed successfully!", flush=True)
        return True, "DONE"

    ret = execute_smart_action(decision)
    if ret is not None and isinstance(ret, tuple):
        return ret
    return False, action

def run_free_ai_bot_loop():
    config = load_ai_config()
    print("====================================================")
    print("�   NON-STOP FREE AI AUTONOMOUS BOT INITIALIZED")
    print(f"�   Provider: {config.get('provider')} ($0.00 Free Mode)")
    print(f"�   Mode: Non-Stop until all tasks complete")
    print("====================================================", flush=True)
    
    # Keep screen awake on phone
    run_adb(["shell", "svc", "power", "stayon", "true"])
    run_adb(["shell", "input", "keyevent", "224"])  # KEYCODE_WAKEUP
    
    # Preload and warm up Ollama model into GPU/RAM so it never times out
    warmup_ollama(config)
    
    delay = config.get("loop_delay_seconds", 2.0)
    loop_num = 0
    consecutive_errors = 0
    
    while True:
        loop_num += 1
        print(f"\n--- [STEP #{loop_num}] Checking Mobile Screen ---", flush=True)
        try:
            # Check if background uninstallation of in.binarybox is due on the 2nd loop
            check_pending_uninstall()

            # Wakeup screen if asleep
            run_adb(["shell", "input", "keyevent", "224"])
            
            is_done, action_taken = decide_and_execute_step(config)
            consecutive_errors = 0
            
            if is_done:
                if action_taken == "PAUSED_FOR_USER":
                    print("�   Bot paused for manual task. Please finish on phone and rerun script when ready.")
                    notify_script_paused("Bot paused for manual task. Please complete on phone.")
                    break
                else:
                    print(f"\n�  �   Task complete / Daily limit reached in {loop_num} steps!")
                    auto_cont = config.get("auto_continue_on_limit", False) or config.get("auto_continue", False)
                    should_continue = prompt_task_complete(
                        "Daily limit reached or current task completed!",
                        auto_continue=auto_cont
                    )
                    if should_continue:
                        LAST_LIMIT_TIME = time.time()
                        print("�  [CONTINUING] Bot will stay active so other tasks can complete.", flush=True)
                        print("�   Please switch to your next task on your phone (resuming in 5s)...", flush=True)
                        time.sleep(5)
                        continue
                    else:
                        print("�   Bot finished and stopped as requested.")
                        break
        except KeyboardInterrupt:
            print("\n�   Stopped by user.")
            notify_script_stopped("Bot stopped by user.")
            break
        except Exception as e:
            consecutive_errors += 1
            print(f"� �  Warning (retrying automatically...): {e}", flush=True)
            if consecutive_errors > 10:
                print("� �  Too many consecutive network errors. Pausing for 5s...", flush=True)
                time.sleep(5)
                consecutive_errors = 0
            
        time.sleep(delay)

if __name__ == "__main__":
    register_exit_sound()
    if len(sys.argv) > 1 and sys.argv[1].lower() in ["bypass-install", "install-bypass", "install"]:
        perform_fake_install_bypass()
    else:
        try:
            run_free_ai_bot_loop()
        except KeyboardInterrupt:
            print("\n�   Stopped by user.")
            notify_script_stopped("Bot stopped by user.")
        except Exception as e:
            print(f"\n�  Unexpected error: {e}", flush=True)
            notify_error(f"Fatal error: {e}")
            raise

