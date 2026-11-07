"""
Reconstruct free_ai_bot.py from pyc strings + corrupted file intact parts.
"""
import marshal

with open('__pycache__/free_ai_bot.cpython-314.pyc', 'rb') as f:
    f.read(16)
    code = marshal.load(f)

funcs = {}
for const in code.co_consts:
    if hasattr(const, 'co_name') and const.co_name != '<module>':
        funcs[const.co_name] = const

# Read corrupted file's intact parts
with open('free_ai_bot.py', 'rb') as f:
    corrupted = f.read().decode('utf-8', errors='replace')

# Extract intact functions from corrupted file
# They are: handle_play_video_and_wait, execute_smart_action, 
# decide_and_execute_step, run_free_ai_bot_loop

def extract_func(text, name):
    idx = text.find(f'def {name}(')
    if idx < 0:
        return None
    # Find next def or end
    rest = text[idx:]
    # Find the end of this function
    lines = rest.split('\n')
    func_lines = []
    for line in lines:
        if line.strip().startswith('def ') and func_lines:
            break
        func_lines.append(line)
    return '\n'.join(func_lines)

# Get intact functions from corrupted file
intact = {}
for name in ['handle_play_video_and_wait', 'execute_smart_action', 'decide_and_execute_step', 'run_free_ai_bot_loop']:
    fn = extract_func(corrupted, name)
    if fn:
        intact[name] = fn
        print(f'Extracted {name}: {len(fn)} chars')

# Now build the complete file
parts = []

# === PART 1: Module header, imports, config, STATE ===
parts.append('''#!/usr/bin/env python3
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

# Try to auto-detect device serial
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

''')

# === PART 2: Helper functions from pyc ===

# load_ai_config already added above

# get_adb
parts.append('''
def get_adb():
    return "adb"
''')

# get_devices
parts.append('''
def get_devices():
    res = subprocess.run([get_adb(), "devices"], capture_output=True, text=True, timeout=10)
    out = res.stdout
    devices = []
    for line in out.splitlines():
        line = line.strip().replace("\\r", "")
        if "List of" in line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[-1] == "device":
            d = parts[0]
            if d and not d.startswith("emulator-"):
                devices.append(d)
    return devices
''')

# select_device
parts.append('''
def select_device(preferred=None):
    devices = get_devices()
    if preferred and preferred in devices:
        return preferred
    for d in devices:
        if d and not d.startswith("emulator-"):
            return d
    return devices[0] if devices else None
''')

# run_adb
parts.append('''
def run_adb(args):
    cmd = [get_adb()]
    if ADB_DEVICE:
        cmd += ["-s", ADB_DEVICE]
    cmd += list(args)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        out = res.stdout.replace("\\r", "")
        return out
    except Exception as e:
        print(f"[ADB Error] {e}", flush=True)
        return None
''')

# tap
parts.append('''
def tap(x, y):
    print(f"\\u2192 [TAP] Clicking on phone at ({x}, {y})", flush=True)
    run_adb(["shell", "input", "tap", str(x), str(y)])
''')

# send_back
parts.append('''
def send_back():
    print("\\u2192 [BACK] Pressing Android Back button", flush=True)
    run_adb(["shell", "input", "keyevent", "4"])
''')

# capture_mobile_screenshot
parts.append('''
def capture_mobile_screenshot(save_path):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(script_dir, save_path)
    run_adb(["shell", "screencap", "-p", "/sdcard/screen.png"])
    run_adb(["pull", "/sdcard/screen.png", full_path])
    return full_path
''')

# extract_task_counter
parts.append('''
def extract_task_counter(elements):
    """Extracts task counter like '9/20', '9 / 20', '7 /' + '15', etc. from screen elements.
    Returns normalized string like '9/20' or None.
    """
    for i, el in enumerate(elements):
        t = (el.get("text") or "").strip()
        m = re.search(r"(\\d+)\\s*/\\s*(\\d+)", t)
        if m:
            return f"{m.group(1)}/{m.group(2)}"
        if m := re.match(r"^(\\d+)\\s*/$", t):
            if i + 1 < len(elements):
                next_t = (elements[i+1].get("text") or "").strip()
                m2 = re.match(r"^/\\s*(\\d+)$", next_t)
                if m2:
                    return f"{m.group(1)}/{m2.group(1)}"
        if m := re.match(r"^/\\s*(\\d+)$", t):
            if i > 0:
                prev_t = (elements[i-1].get("text") or "").strip()
                m1 = re.match(r"^(\\d+)\\s*/$", prev_t)
                if m1:
                    return f"{m1.group(1)}/{m.group(1)}"
    return None
''')

# check_pending_uninstall
parts.append('''
def check_pending_uninstall():
    """Checks if background deletion of in.binarybox is due on the 2nd loop."""
    loops = QUIZ_STATE.get("pending_uninstall_loops", 0)
    if loops and loops > 0:
        print(f"\\u23f3 [INSTALL BYPASS] Countdown to background uninstall: {loops} loop(s) remaining.", flush=True)
        QUIZ_STATE["pending_uninstall_loops"] = loops - 1
        if loops <= 1:
            print("\\u274c [BACKGROUND] Deleting/Uninstalling in.binarybox.blackscreen in background...", flush=True)
            res = run_adb(["uninstall", DUMMY_PACKAGE])
            if res and "Success" in res:
                print("\\u274c [BACKGROUND] Finished removing in.binarybox.blackscreen (Success). Tasks continue seamlessly!", flush=True)
            else:
                print(f"\\u26a0\\ufe0f [BACKGROUND] Uninstall result: {res}", flush=True)
            QUIZ_STATE["pending_uninstall_loops"] = None
            return True
    return False
''')

# alert_user_on_laptop_and_mobile
parts.append('''
def alert_user_on_laptop_and_mobile(reason):
    """Alerts user loudly on BOTH Laptop and Mobile Phone when manual intervention is needed."""
    print("\\n\\U0001f514 ===================================================", flush=True)
    print("\\U0001f6a8 [ATTENTION NEEDED] MANUAL TASK / INTERVENTION REQUIRED!", flush=True)
    print(f"\\U0001f6a8 Reason: {reason}", flush=True)
    print("\\U0001f50a Triggering sound and vibration alert on Mobile Phone & Laptop...", flush=True)
    print("\\U0001f514 ===================================================\\n", flush=True)
    # Mobile alert
    try:
        play_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sound_notifier.py")
        if os.path.exists(play_script):
            subprocess.Popen([sys.executable, play_script, "alert"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    # Laptop alert
    try:
        import winsound
        for _ in range(3):
            winsound.Beep(1200, 350)
            time.sleep(0.1)
        winsound.Beep(1200, 350)
    except Exception:
        print("\\u0007\\u0007\\u0007", flush=True)
''')

# get_ui_elements
parts.append('''
def get_ui_elements():
    xml_data = run_adb(["shell", "uiautomator", "dump", "/sdcard/ui.xml"])
    if not xml_data:
        return []
    # The dump prints "UI hierarchy dumped to: /sdcard/ui.xml"
    # Pull the XML
    res = subprocess.run([get_adb(), "pull", "/sdcard/ui.xml", os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ui.xml")],
                         capture_output=True, text=True)
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ui.xml"), "r", encoding="utf-8") as f:
            xml_content = f.read()
    except Exception:
        return []
    
    import xml.etree.ElementTree as ET
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
        m = re.search(r"\\[(\\d+),(\\d+)\\]\\s*\\[(\\d+),(\\d+)\\]", bounds_str)
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
''')

# compress_image_for_ai
parts.append('''
def compress_image_for_ai(img_path, target_width):
    import PIL.Image
    out_path = img_path.rsplit(".", 1)[0] + "_ai.jpg"
    abs_in = os.path.abspath(img_path)
    abs_out = os.path.abspath(out_path)
    try:
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
    # Fallback: use powershell to resize
    ps_cmd = (
        f"Add-Type -AssemblyName System.Drawing;"
        f"$src = [System.Drawing.Image]::FromFile('{abs_in}');"
        f"$ow = $src.Width; $oh = $src.Height;"
        f"$tw = {target_width};"
        f"$th = [int]($oh * ($tw / $ow));"
        f"$dst = New-Object System.Drawing.Bitmap $tw, $th;"
        f"$gr = [System.Drawing.Graphics]::FromImage($dst);"
        f"$gr.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic;"
        f"$gr.DrawImage($src, 0, 0, $tw, $th);"
        f"$dst.Save('{abs_out}', [System.Drawing.Imaging.ImageFormat]::Jpeg);"
        f"$gr.Dispose(); $dst.Dispose(); $src.Dispose();"
        f"Write-Output \\"{ow},{oh},{tw},{th}\\""
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
''')

# call_gemini_vision  
parts.append('''
def call_gemini_vision(img_path, prompt, config):
    """Free Tier Gemini Vision via Google AI Studio API key"""
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
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt + f"\\nNote: Image dimensions are {orig_w}x{orig_h}. Return x, y coordinates based on this \\n{image} image."},
                {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}
            ]
        }],
        "generationConfig": {"temperature": 0.1},
        "responseMimeType": "application/json"
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    try:
        req = subprocess.run(
            ["curl", "-s", "-X", "POST", url,
             "-H", "Content-Type: application/json",
             "-d", data_bytes.decode("utf-8")],
            capture_output=True, text=True, timeout=30)
        resp = req.stdout
        data = json.loads(resp)
        ans_text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return json.loads(ans_text) if ans_text else None
    except Exception as e:
        print(f"\\u26a0\\ufe0f [Gemini Vision Error] {e}", flush=True)
        return None
''')

# call_ollama_vision
parts.append('''
def call_ollama_vision(img_path, prompt, config):
    """100% Free & Offline Local Ollama Vision Model on your laptop"""
    host = config.get("ollama_host", "http://localhost:11434")
    model = config.get("ollama_vision_model", "llama3.2-vision")
    comp_path, orig_w, orig_h = compress_image_for_ai(img_path, 1080)
    try:
        import base64
        with open(comp_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None
    payload = {
        "model": model,
        "prompt": prompt + f"\\nNote: Image dimensions are {orig_w}x{orig_h}. Return x, y coordinates based on this \\n{image} image.",
        "images": [img_b64],
        "format": "json",
        "stream": False,
        "keep_alive": "5m"
    }
    url = f"{host}/api/generate"
    try:
        req = subprocess.run(
            ["curl", "-s", "-X", "POST", url,
             "-H", "Content-Type: application/json",
             "-d", json.dumps(payload)],
            capture_output=True, text=True, timeout=120)
        resp = json.loads(req.stdout)
        res = resp.get("response", "{}")
        return json.loads(res) if res else {}
    except Exception as e:
        print(f"\\u26a0\\ufe0f [Ollama Vision Error] {e}", flush=True)
        return {}
''')

# === PART 3: perform_fake_install_bypass (RECONSTRUCTED with fixes) ===
parts.append('''
def perform_fake_install_bypass():
    """
    Bypasses mandatory app installation tasks when a quiz repeats 3 times:
    1. Goes to Home screen
    2. Installs in.binarybox.blackscreen for ad installation.apk via ADB
    3. Opens it for 5 seconds
    4. Switches back to our app (e.g. com.shake.master)
    5. Clicks the 'Add Bonus' button if present
    6. Continues the task
    7. Schedules background deletion of in.binarybox on the 2nd loop so tasks continue seamlessly.
    """
    print("\\n\\u274c ====================================================", flush=True)
    print("\\U0001f680 [INSTALL BYPASS] Triggered: Bypassing Ad Installation!", flush=True)
    print("\\U0001f4e6 ====================================================", flush=True)

    app_pkg = get_current_app_package()
    if app_pkg:
        QUIZ_STATE["target_app_package"] = app_pkg
    target_app = QUIZ_STATE.get("target_app_package", "com.shake.master")

    # Step 1: Go to Home screen
    print("\\u2b26\\U0001f3e0 [STEP 1] Going to phone Home Screen...", flush=True)
    run_adb(["shell", "input", "keyevent", "3"])
    time.sleep(1.5)

    # Step 2: Install APK via ADB
    print(f"\\u2b25 [STEP 2] Installing '{os.path.basename(DUMMY_APK_PATH)}'...", flush=True)
    if os.path.exists(DUMMY_APK_PATH):
        run_adb(["uninstall", DUMMY_PACKAGE])
        res = run_adb(["install", "-r", "-g", DUMMY_APK_PATH])
        print(f"   Install Status: {res}", flush=True)
    else:
        print(f"\\u26a0\\ufe0f APK file not found at: {DUMMY_APK_PATH}", flush=True)

    # Step 3: Open for 5 seconds
    print(f"\\u23f1\\U0001f4f9 [STEP 3] Opening {DUMMY_PACKAGE} for 5 seconds...", flush=True)
    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])
    time.sleep(5)

    # [BYPASS VERIFY] After opening dummy app, check we are in dummy app (not Play Store)
    _op_pkg = get_current_app_package()
    if _op_pkg and _op_pkg != DUMMY_PACKAGE:
        print(f"? [BYPASS VERIFY] Open returned to \\'{_op_pkg}\\' not dummy. Dismissing...", flush=True)
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
    print(f"\\U0001f509 [STEP 4] Switching back to our app ({target_app})...", flush=True)
    run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])
    time.sleep(2.5)

    # [VERIFY] Confirm we are back in target app
    _back_pkg = get_current_app_package()
    if _back_pkg != target_app:
        print(f"? [BYPASS VERIFY] Return failed (got \\'{_back_pkg}\\' not \\'{target_app}\\'). Force-launching...", flush=True)
        for _fi in range(5):
            run_adb(["shell", "input", "keyevent", "3"])
            time.sleep(0.5)
            run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])
            time.sleep(3.0)
            _bp = get_current_app_package()
            if _bp == target_app:
                print(f"? [BYPASS VERIFY] Force-launch OK on attempt {_fi+1}.", flush=True)
                break

    # Step 5: Check screen according to actual UI elements (No blind forced click)
    print("\\U0001f50d [STEP 5] Checking screen after returning to app...", flush=True)
    elements = get_ui_elements()
    clicked_action = False

    # Check if 'Add Bonus' button is actually visible
    for e in elements:
        t = e.get("text", "").strip().lower()
        if "add bonus" in t or t == "add" or "claim" in t or "collect" in t:
            print(f"\\U0001f3e1 Found \\'{e[\\'text\\']}\\' button -> Tapping ({e[\\'bounds\\'][\\'cx\\']}, {e[\\'bounds\\'][\\'cy\\']})", flush=True)
            tap(e["bounds"]["cx"], e["bounds"]["cy"])
            clicked_action = True
            time.sleep(1.5)
            break

    # Check if a close / dialog button is visible instead
    if not clicked_action:
        for e in elements:
            t = e.get("text", "").strip().lower()
            if t in ["close", "skip", "dismiss", "ok", "cancel"] or (e.get("clickable") and "close" in t):
                print(f"\\u26a1 Found dialog button \\'{e[\\'text\\']}\\' -> Tapping ({e[\\'bounds\\'][\\'cx\\']}, {e[\\'bounds\\'][\\'cy\\']})", flush=True)
                tap(e["bounds"]["cx"], e["bounds"]["cy"])
                clicked_action = True
                time.sleep(1)
                break

    if not clicked_action:
        print("\\u2139\\ufe0f No \\'Add Bonus\\' popup detected. Proceeding to main bot loop to decide according to screen.", flush=True)
    time.sleep(1)

    # Step 6: Schedule deletion in 2nd loop in background
    QUIZ_STATE["pending_uninstall_loops"] = 2
    QUIZ_STATE["repeat_count"] = 0
    QUIZ_STATE["last_quiz_id"] = None
    print("\\u2787\\U0001f533 [STEP 6] Scheduled deletion of in.binarybox in 2nd loop in background.", flush=True)
    print("\\u2705 [INSTALL BYPASS COMPLETE] Continuing bot task without interruption!\\n", flush=True)
    return True
''')

# === PART 4: dismiss_ad_if_present ===
parts.append('''
def dismiss_ad_if_present():
    """Dismisses top-right close \\'X\\' or dialog close if an ad popup is showing."""
    elements = get_ui_elements()
    for e in elements:
        t = (e.get("text") or "").strip().lower()
        if t in ["close", "close ad", "skip", "dismiss"] or (e.get("clickable") and "close" in t):
            print(f"\\u274c Found ad close button \\'{e[\\'text\\']}\\' -> Tapping ({e[\\'bounds\\'][\\'cx\\']}, {e[\\'bounds\\'][\\'cy\\']})", flush=True)
            tap(e["bounds"]["cx"], e["bounds"]["cy"])
            return True
    # Fallback: tap common top-right close area
    print("\\u274c Tapping common top-right ad cross area (1013, 176)...", flush=True)
    tap(1013, 176)
    return False
''')

# === PART 5: handle_add_bonus_and_wait (RECONSTRUCTED with install-before-ad-close fix) ===
parts.append('''
def handle_add_bonus_and_wait():
    """
    Executes the user\\'s exact quiz completion flow:
    1. Click \\'Add Bonus\\' button
    2. Check for install task BEFORE dismissing ad
    3. If install task: run install bypass (install app -> open -> close -> back to app)
    4. Then dismiss ad overlay
    5. Read screen: If same question counter remains -> alert user with sound on laptop & mobile!
    """
    prev_counter = STATE.get("last_task_counter", "")
    print(f"\\n\\U0001f3e1 [BONUS] Tapping \\'Add Bonus\\' for Task \\'{prev_counter}\\'...", flush=True)

    # 1. Tap Add Bonus button (find in elements or fallback to 500, 1705)
    elements = get_ui_elements()
    tapped = False
    for e in elements:
        t = e.get("text", "").strip().lower()
        if "add bonus" in t or t == "add":
            print(f"\\u2192 Found \\'{e[\\'text\\']}\\' button -> Tapping ({e[\\'bounds\\'][\\'cx\\']}, {e[\\'bounds\\'][\\'cy\\']})", flush=True)
            tap(e["bounds"]["cx"], e["bounds"]["cy"])
            tapped = True
            break
    if not tapped:
        print("\\u2192 Tapping \\'Add Bonus\\' default coordinates at (500, 1705)...", flush=True)
        tap(500, 1705)
    # 2. Check for install task BEFORE dismissing ad
    print("\\n\\U0001f50d [AD CHECK] Checking if install task needs handling before closing ad...", flush=True)
    ad_elements = get_ui_elements()
    install_task_found = False
    for ad_e in ad_elements:
        ad_t = (ad_e.get("text") or "").strip().lower()
        if any(kw in ad_t for kw in ["play video", "final watch", "watch to unlock", "watch video", "install", "open app"]):
            print(f"\\u2192 [INSTALL TASK] Detected install task: {ad_e.get(\\'text\\', \\'\\')} -> Running install bypass BEFORE closing ad...", flush=True)
            perform_fake_install_bypass()
            install_task_found = True
            break
    if not install_task_found:
        print("\\n\\U0001f50d [AD FINISHED] No install task - dismissing ad overlay...", flush=True)
        dismiss_ad_if_present()
    time.sleep(2)

    # 3. Read screen to verify if question counter advanced
    new_elements = get_ui_elements()
    new_counter = extract_task_counter(new_elements)

    if new_counter:
        print(f"\\U0001f4ca [SCREEN READ] Task counter after full 25s quiz cycle: \\'{new_counter}\\' (Before: \\'{prev_counter}\\')", flush=True)
        if prev_counter and new_counter == prev_counter:
            if QUIZ_STATE["last_quiz_id"] == new_counter:
                QUIZ_STATE["repeat_count"] += 1
            else:
                QUIZ_STATE["last_quiz_id"] = new_counter
                QUIZ_STATE["repeat_count"] = 1
            print(f"\\U0001f501 [QUIZ REPEAT] Task counter \\'{new_counter}\\' repeated ({QUIZ_STATE[\\'repeat_count\\']}/3 loops)", flush=True)
            if QUIZ_STATE["repeat_count"] >= 3:
                print(f"\\U0001f680 [TRIGGER BYPASS] Task counter \\'{new_counter}\\' repeated 3 times in 3 loops!", flush=True)
                perform_fake_install_bypass()
                QUIZ_STATE["last_quiz_id"] = None
                QUIZ_STATE["repeat_count"] = 0
                return False, "INSTALL_BYPASS_EXECUTED"
            print(f"\\u2139 Counter \\'{new_counter}\\' seen {QUIZ_STATE[\\'repeat_count\\']}/3 times. Continuing bot task...", flush=True)
        else:
            # Successfully advanced!
            print(f"\\U0001f389 [PROGRESS] Question advanced from \\'{prev_counter}\\' -> \\'{new_counter}\\'! Full quiz task completed.\\n", flush=True)
            STATE["last_task_counter"] = new_counter
            STATE["counter_seen_time"] = time.time()
    else:
        print("\\u2139 Screen changed or ad dismissed. Returning to main decision loop.\\n", flush=True)

    return False, "COMPLETED_QUIZ_CYCLE"
''')

# === PART 6: get_current_app_package (missing from pyc but needed) ===
parts.append('''
def get_current_app_package():
    """Get the currently focused app package name."""
    try:
        res = subprocess.run(
            [get_adb(), "shell", "dumpsys", "window"],
            capture_output=True, text=True, timeout=10)
        for line in res.stdout.splitlines():
            if "mCurrentFocus" in line:
                import re as _re
                m = _re.search(r"u0\\s+([a-zA-Z0-9_.]+)", line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return None
''')

# === PART 7: Append intact functions from corrupted file ===
for name in ['handle_play_video_and_wait', 'execute_smart_action', 'decide_and_execute_step', 'run_free_ai_bot_loop']:
    if name in intact:
        parts.append(intact[name])
        print(f'Appended intact {name}')
    else:
        print(f'WARNING: {name} not found in corrupted file')

# Write the reconstructed file
output = '\n'.join(parts)
with open('free_ai_bot_reconstructed.py', 'w', encoding='utf-8') as f:
    f.write(output)

print(f'\nWrote {len(output)} bytes to free_ai_bot_reconstructed.py')

# Syntax check
import py_compile
try:
    py_compile.compile('free_ai_bot_reconstructed.py', doraise=True)
    print('SYNTAX OK')
except Exception as e:
    print(f'SYNTAX ERROR: {e}')
