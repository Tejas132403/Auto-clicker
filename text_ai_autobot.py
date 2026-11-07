import os
import sys
import time
import json
import re
import subprocess
import threading
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

from sound_notifier import (
    play_sound,
    prompt_task_complete,
    notify_task_complete,
    notify_script_stopped,
    notify_script_paused,
    notify_error,
    register_exit_sound
)

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AI_CONFIG_FILE = os.path.join(SCRIPT_DIR, "ai_config.json")

DUMMY_APK_PATH = os.path.join(SCRIPT_DIR, "in.binarybox.blackscreen for ad installation.apk")
DUMMY_PACKAGE = "in.binarybox.blackscreen"

QUIZ_STATE = {
    "last_quiz_id": None,
    "repeat_count": 0,
    "pending_uninstall_loops": -1,
    "target_app_package": "com.shake.master"
}

# Candidate ADB paths
ADB_CANDIDATES = [
    r"C:\Users\tejas\AppData\Local\Android\Sdk\platform-tools\adb.exe",
    r"D:\mirzapur\scrcpy-win64-v3.2\platform-tools\adb.exe",
    "adb"
]

def get_adb():
    for p in ADB_CANDIDATES:
        if os.path.exists(p):
            return p
    return "adb"

ADB = get_adb()

def load_config():
    cfg = {
        "provider": "ollama",
        "ollama_host": "http://localhost:11434",
        "ollama_model": "llama3.2:latest",
        "gemini_api_key": "",
        "gemini_model": "models/gemma-4-26b-a4b-it",
        "interval_seconds": 1.0
    }
    if os.path.exists(AI_CONFIG_FILE):
        try:
            with open(AI_CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                cfg.update(loaded)
        except Exception:
            pass
    return cfg

ACTIVE_DEVICE = None

def get_devices():
    try:
        res = subprocess.run([ADB, "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = res.stdout.decode("utf-8", errors="replace").strip()
        devices = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("*") or line.startswith("List of"):
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
    except Exception:
        return []

def select_device(preferred=None):
    global ACTIVE_DEVICE
    devices = get_devices()
    if not devices:
        return None
    if preferred and preferred in devices:
        ACTIVE_DEVICE = preferred
        return ACTIVE_DEVICE
    # If multiple devices, prioritize physical USB phone over emulator
    physical = [d for d in devices if not d.startswith("emulator-")]
    ACTIVE_DEVICE = physical[0] if physical else devices[0]
    return ACTIVE_DEVICE

def run_adb(args):
    global ACTIVE_DEVICE
    if not ACTIVE_DEVICE:
        select_device()
    cmd = [ADB]
    if ACTIVE_DEVICE:
        cmd += ["-s", ACTIVE_DEVICE]
    cmd += args
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout_text = res.stdout.decode("utf-8", errors="replace").strip()
        stderr_text = res.stderr.decode("utf-8", errors="replace").strip()
        if res.returncode != 0 and stderr_text:
            if "more than one device" in stderr_text or "not found" in stderr_text or "offline" in stderr_text:
                select_device()
        return stdout_text
    except Exception as e:
        print(f"[ADB Error] {e}", flush=True)
        return ""

def ensure_screen_awake():
    """Wakes up screen and keeps it on while bot runs."""
    run_adb(["shell", "input", "keyevent", "224"])  # KEYCODE_WAKEUP
    run_adb(["shell", "svc", "power", "stayon", "true"])

def tap(x, y):
    print(f"👉 [TAP] Tapping on screen at ({x}, {y})", flush=True)
    run_adb(["shell", "input", "tap", str(x), str(y)])

def send_back():
    print("🔙 [BACK] Pressing Android Back button", flush=True)
    run_adb(["shell", "input", "keyevent", "4"])

def parse_bounds(b_str):
    m = re.findall(r"\[(\d+),(\d+)\]", b_str)
    if len(m) == 2:
        x1, y1 = int(m[0][0]), int(m[0][1])
        x2, y2 = int(m[1][0]), int(m[1][1])
        return {
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "cx": (x1 + x2) // 2,
            "cy": (y1 + y2) // 2
        }
    return None

def get_screen_ui():
    """
    Extracts all UI hierarchy nodes without vision/photo/OCR.
    Returns list of dicts with text, id, clickable, bounds, cx, cy
    """
    # 1. Try compressed dump first (faster, avoids idletime animation stalls)
    run_adb(["shell", "uiautomator", "dump", "--compressed", "/sdcard/window_dump.xml"])
    xml_data = run_adb(["shell", "cat", "/sdcard/window_dump.xml"])
    
    # 2. Fallback to standard dump if compressed was not generated
    if not xml_data or "<hierarchy" not in xml_data:
        run_adb(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"])
        xml_data = run_adb(["shell", "cat", "/sdcard/window_dump.xml"])
        
    if not xml_data or "<hierarchy" not in xml_data:
        return []
    
    elements = []
    try:
        root = ET.fromstring(xml_data[xml_data.find("<hierarchy"):])
        for node in root.iter("node"):
            text = node.attrib.get("text", "").strip()
            desc = node.attrib.get("content-desc", "").strip()
            val = text if text else desc
            bounds_str = node.attrib.get("bounds", "")
            clickable = node.attrib.get("clickable", "false") == "true"
            res_id = node.attrib.get("resource-id", "").split("/")[-1]
            
            b = parse_bounds(bounds_str)
            if b:
                elements.append({
                    "text": val,
                    "id": res_id,
                    "clickable": clickable,
                    "bounds": b,
                    "cx": b["cx"],
                    "cy": b["cy"]
                })
    except Exception as e:
        print(f"[XML Parse Error] {e}", flush=True)
    return elements

def extract_task_counter(elements):
    """
    Extracts task counter like '9/20', '9 / 20', '7 /' + '15', etc. from screen elements.
    Returns normalized string like '9/20' or None.
    """
    for i, el in enumerate(elements):
        t = (el.get("text") or "").strip()
        # Case 1: '9/20' or '9 / 20' in a single element
        m = re.search(r"(\d+)\s*/\s*(\d+)", t)
        if m:
            return f"{m.group(1)}/{m.group(2)}"
            
        # Case 2: '9 /' in current element, '20' in next element
        m1 = re.search(r"^(\d+)\s*/$", t)
        if m1 and i + 1 < len(elements):
            next_t = (elements[i+1].get("text") or "").strip()
            if next_t.isdigit():
                return f"{m1.group(1)}/{next_t}"
                
        # Case 3: '9' in current element, '/ 20' in next element
        if t.isdigit() and i + 1 < len(elements):
            next_t = (elements[i+1].get("text") or "").strip()
            m2 = re.search(r"^/\s*(\d+)$", next_t)
            if m2:
                return f"{t}/{m2.group(1)}"
                
        # Case 4: '9', '/', '20' across 3 elements
        if t.isdigit() and i + 2 < len(elements):
            slash_t = (elements[i+1].get("text") or "").strip()
            next_t = (elements[i+2].get("text") or "").strip()
            if slash_t == "/" and next_t.isdigit():
                return f"{t}/{next_t}"
                
    return None

def get_current_app_package():
    """Detects active foreground package, ignoring launcher/systemui."""
    try:
        out = run_adb(["shell", "dumpsys", "window", "displays"])
        m = re.search(r"mControlTarget=Window\{[0-9a-fA-F]+\s+u\d+\s+([a-zA-Z0-9_\.]+)/", out)
        if m:
            pkg = m.group(1).strip()
            if pkg and not any(x in pkg.lower() for x in ["launcher", "systemui", "upslide", "inputmethod", "binarybox"]):
                return pkg
        for line in out.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                m2 = re.search(r"([a-zA-Z0-9_\.]+)[\/\.]", line)
                if m2:
                    pkg2 = m2.group(1).strip()
                    if pkg2 and not any(x in pkg2.lower() for x in ["launcher", "systemui", "upslide", "inputmethod", "binarybox"]):
                        return pkg2
    except Exception:
        pass
    return "com.shake.master"

def check_pending_uninstall():
    """Checks if background deletion of in.binarybox is due on the 2nd loop."""
    if QUIZ_STATE.get("pending_uninstall_loops", -1) > 0:
        QUIZ_STATE["pending_uninstall_loops"] -= 1
        print(f"⏳ [INSTALL BYPASS] Countdown to background uninstall: {QUIZ_STATE['pending_uninstall_loops']} loop(s) remaining.", flush=True)
        if QUIZ_STATE["pending_uninstall_loops"] == 0:
            QUIZ_STATE["pending_uninstall_loops"] = -1
            def _bg_uninstall():
                print(f"\n🗑️ [BACKGROUND] Deleting/Uninstalling {DUMMY_PACKAGE} in background...", flush=True)
                res = run_adb(["uninstall", DUMMY_PACKAGE])
                print(f"🗑️ [BACKGROUND] Finished removing {DUMMY_PACKAGE} ({res}). Tasks continue seamlessly!\n", flush=True)
            threading.Thread(target=_bg_uninstall, daemon=True).start()

def perform_fake_install_bypass():
    """
    Bypasses mandatory app installation tasks when a quiz repeats 3 times:
    1. Records current app package (e.g. com.shake.master)
    2. Goes to Home screen
    3. Installs in.binarybox.blackscreen for ad installation.apk via ADB
    4. Opens it for 5 seconds
    5. Switches back to our app
    6. Continues the task
    7. Schedules background deletion of in.binarybox on the 2nd loop so tasks continue seamlessly.
    """
    print("\n📦 ====================================================", flush=True)
    print("🚀 [INSTALL BYPASS] Triggered: Bypassing Ad Installation!", flush=True)
    print("📦 ====================================================", flush=True)

    # Detect current app before leaving
    app_pkg = get_current_app_package()
    if app_pkg:
        QUIZ_STATE["target_app_package"] = app_pkg
    target_app = QUIZ_STATE.get("target_app_package", "com.shake.master")

    # Step 1: Go to Home screen
    print("🏠 [STEP 1] Going to phone Home Screen...", flush=True)
    run_adb(["shell", "input", "keyevent", "3"])
    time.sleep(1.5)

    # Step 2: Install APK via ADB
    print(f"📲 [STEP 2] Installing '{os.path.basename(DUMMY_APK_PATH)}'...", flush=True)
    if os.path.exists(DUMMY_APK_PATH):
        # Uninstall prior version first to ensure a clean install
        run_adb(["uninstall", DUMMY_PACKAGE])
        res = run_adb(["install", "-r", "-g", DUMMY_APK_PATH])
        print(f"   Install Status: {res}", flush=True)
    else:
        print(f"⚠️ APK file not found at: {DUMMY_APK_PATH}", flush=True)

    # Step 3: Open for 5 seconds
    print(f"⏱️ [STEP 3] Opening {DUMMY_PACKAGE} for 5 seconds...", flush=True)
    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])
    time.sleep(5)

    # Step 4: Return to our app
    print(f"🔙 [STEP 4] Switching back to our app ({target_app})...", flush=True)
    run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])
    time.sleep(2.5)

    # Step 5: Check screen according to actual UI elements (claim bonus if present)
    print("🔍 [STEP 5] Checking screen after returning to app...", flush=True)
    elements = get_screen_ui()
    for e in elements:
        t = (e.get("text") or "").strip().lower()
        if "add bonus" in t or t == "add" or "claim" in t or "collect" in t:
            print(f"🎁 Found '{e['text']}' button -> Tapping ({e['cx']}, {e['cy']})", flush=True)
            tap(e['cx'], e['cy'])
            time.sleep(2)
            break

    # Step 6: Schedule deletion in 2nd loop in background
    QUIZ_STATE["pending_uninstall_loops"] = 2
    QUIZ_STATE["repeat_count"] = 0
    QUIZ_STATE["last_quiz_id"] = None
    print("🗓️ [STEP 6] Scheduled deletion of in.binarybox in 2nd loop in background.", flush=True)
    print("✅ [INSTALL BYPASS COMPLETE] Continuing bot task without interruption!\n", flush=True)
    return True

DEFAULT_OPTION_COORDS = {
    "A": (540, 1328),
    "B": (540, 1502),
    "C": (540, 1676),
    "D": (540, 1850)
}

def extract_quiz_info(elements):
    """
    Extracts the quiz question and all available options (A, B, C, D)
    with their exact screen coordinates.
    """
    question = None
    options = {}
    
    # 1. Detect question
    for el in elements:
        t = el.get("text", "").strip()
        rid = el.get("id", "")
        if rid == "tvQuestion" or "?" in t or any(w in t for w in ["खिलाड़ी", "कितने", "किस", "कौन", "क्या", "कहाँ", "कब", "game"]):
            question = t
            break
            
    # Fallback for question
    if not question:
        for el in elements:
            t = el.get("text", "").strip()
            if len(t) > 10 and not any(b in t.lower() for b in ["bonus", "wait", "sec", "video", "quiz"]):
                if not re.search(r"^\d+\s*/\s*\d+$", t):
                    question = t
                    break
                    
    # 2. Extract options (A, B, C, D)
    for i, el in enumerate(elements):
        t = el.get("text", "").strip()
        m = re.match(r"^([A-Da-d])\.?$", t)
        if m:
            lbl = m.group(1).upper()
            text_val = ""
            def_x, def_y = DEFAULT_OPTION_COORDS.get(lbl, (540, 1328))
            cx, cy = def_x, def_y
            
            # The next element contains option text
            if i + 1 < len(elements):
                next_el = elements[i + 1]
                next_t = next_el.get("text", "").strip()
                if not re.match(r"^[A-Da-d]\.?$", next_t):
                    text_val = next_t
                    if next_el.get("cx") and next_el.get("cy"):
                        cx, cy = next_el["cx"], next_el["cy"]
            
            options[lbl] = {
                "text": text_val,
                "cx": cx,
                "cy": cy
            }
            
    # Check if options mapped; if partial, populate defaults
    if options:
        for lbl in ["A", "B", "C", "D"]:
            if lbl not in options:
                def_x, def_y = DEFAULT_OPTION_COORDS[lbl]
                options[lbl] = {"text": "", "cx": def_x, "cy": def_y}
                
    return question, options

def parse_ollama_json(raw_text):
    """
    Robust JSON parser for Ollama.
    Handles complete JSON, truncated JSON, unclosed quotes, and plain text.
    """
    if not raw_text:
        return None
    raw_text = raw_text.strip()
    
    # 1. Standard JSON parse
    try:
        return json.loads(raw_text)
    except Exception:
        pass
        
    # 2. JSON enclosed in braces
    m = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
            
    # 3. Resilient regex extraction (works even if output was truncated!)
    res = {}
    m_opt = re.search(r'["\']?(?:selected_option|correct_option|option)["\']?\s*:\s*["\']?([A-Da-d])["\']?', raw_text)
    if m_opt:
        res["selected_option"] = m_opt.group(1).upper()
        
    m_txt = re.search(r'["\']?(?:option_text|target_name)["\']?\s*:\s*["\']([^"\'}\n\r]+)["\']?', raw_text)
    if m_txt:
        res["option_text"] = m_txt.group(1).strip()
        
    m_rsn = re.search(r'["\']?reason["\']?\s*:\s*["\']?([^"\'}\n\r]+)["\']?', raw_text)
    if m_rsn:
        res["reason"] = m_rsn.group(1).strip()
        
    if "selected_option" in res or "option_text" in res:
        return res
        
    # 4. Fallback search for letter in raw text (e.g. "Option A" or "Answer: B")
    for lbl in ["A", "B", "C", "D"]:
        if re.search(rf"\b(?:option|answer|choice)?\s*[:\-\s]?\s*{lbl}\b", raw_text, re.IGNORECASE):
            return {"selected_option": lbl, "reason": raw_text[:100]}
            
    return None

def warmup_ollama(config):
    """
    Preloads the Ollama model into GPU/RAM at script startup so subsequent
    queries respond instantly with 0 latency and never hit a cold-start timeout.
    Also sets keep_alive to -1 so Ollama never unloads the model from RAM after 5 minutes.
    """
    host = config.get("ollama_host", "http://127.0.0.1:11434").replace("localhost", "127.0.0.1")
    model = config.get("ollama_model", "llama3.2:latest")
    url = f"{host}/api/generate"
    payload = {
        "model": model,
        "keep_alive": -1
    }
    print(f"🦙 Preloading & warming up Ollama model ({model}) in memory...", flush=True)
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"✅ Local Ollama ({model}) is preloaded & resident in memory (0s latency mode ready)!", flush=True)
            return True
    except Exception as e:
        print(f"⚠️ [Ollama Warmup Notice] {e} (Will connect dynamically during cycles)", flush=True)
        return False

def ask_gemini_quiz(question, options, config):
    """
    Instant fallback to Gemini API if local Ollama times out or fails.
    """
    api_key = config.get("gemini_api_key", "").strip()
    if not api_key:
        return None
    
    opts_str = "\n".join([f"{k}. {v['text']}" for k, v in sorted(options.items()) if v.get("text")])
    prompt = f"""You are an expert mobile gaming quiz solver (Free Fire, BGMI, PUBG, etc.).
Question: {question}

Options:
{opts_str}

Analyze carefully: Which option is the correct answer to the question?
Return JSON strictly in this format:
{{"selected_option": "A" or "B" or "C" or "D", "option_text": "<text of chosen option>", "reason": "<short explanation>"}}
"""
    model_name = config.get("gemini_model", "models/gemma-4-26b-a4b-it")
    clean_model = model_name.split("/")[-1] if "/" in model_name else model_name
    models_to_try = [clean_model, "gemini-2.0-flash", "gemini-1.5-flash"]
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 200, "responseMimeType": "application/json"}
    }
    
    for m in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                parsed = parse_ollama_json(text)
                if parsed:
                    return parsed
        except Exception:
            continue
    return None

def ask_ollama_quiz(question, options, config):
    """
    Sends the question and options to Ollama (llama3.2:latest).
    Ollama returns the chosen option letter (A, B, C, or D).
    Uses keep_alive=-1 so the model stays permanently loaded in memory.
    """
    host = config.get("ollama_host", "http://127.0.0.1:11434").replace("localhost", "127.0.0.1")
    model = config.get("ollama_model", "llama3.2:latest")
    
    opts_str = "\n".join([f"{k}. {v['text']}" for k, v in sorted(options.items()) if v.get("text")])
    if not opts_str:
        opts_str = "\n".join([f"{k}." for k in sorted(options.keys())])
        
    prompt = f"""You are an expert gaming quiz solver (Free Fire, PUBG, BGMI, and mobile gaming).
Question: {question}

Options:
{opts_str}

Analyze carefully: Which option is the correct answer to the question?
Return JSON strictly in this format:
{{"selected_option": "A" or "B" or "C" or "D", "option_text": "<text of chosen option>", "reason": "<short explanation>"}}
"""

    payload = {
        "model": model,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "keep_alive": -1,
        "options": {
            "temperature": 0.0,
            "num_predict": 200
        }
    }
    
    url = f"{host}/api/generate"
    timeout_sec = int(config.get("ollama_timeout", 60))
    for attempt in range(1, 3):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ans_str = data.get("response", "").strip()
                parsed = parse_ollama_json(ans_str)
                if parsed:
                    return parsed
        except Exception as e:
            if attempt == 1:
                print(f"[Ollama Warning] Attempt 1 failed ({e}). Retrying in 1s...", flush=True)
                time.sleep(1)
            else:
                print(f"[Ollama Error] {e}", flush=True)
    return None

def resolve_option_click(decision, options):
    """
    Matches Ollama's answer to the exact option letter ('A', 'B', 'C', 'D')
    and retrieves exact screen (x, y) coordinates.
    NEVER blindly defaults to Option A!
    """
    if not decision or not options:
        return None, None, None, None
        
    selected_opt = str(decision.get("selected_option") or decision.get("correct_option") or decision.get("option") or "").strip().upper()
    opt_text = str(decision.get("option_text") or decision.get("target_name") or "").strip().lower()
    reason = str(decision.get("reason") or "").strip()
    reason_low = reason.lower()
    
    # 1. Direct option letter match (A, B, C, D)
    if selected_opt in ["A", "B", "C", "D"] and selected_opt in options:
        opt_info = options[selected_opt]
        return selected_opt, opt_info["cx"], opt_info["cy"], f"Ollama selected Option {selected_opt}: '{opt_info['text']}' ({reason})"
        
    # 2. Check if option letter was mentioned in reason
    for lbl in ["A", "B", "C", "D"]:
        patterns = [
            rf"option\s+{lbl.lower()}\b",
            rf"\({lbl.lower()}\)",
            rf"['\"]{lbl.lower()}['\"]",
            rf"\b{lbl.lower()}\.\s*",
            rf"choice\s+{lbl.lower()}\b"
        ]
        if any(re.search(p, reason_low) for p in patterns):
            if lbl in options:
                opt_info = options[lbl]
                return lbl, opt_info["cx"], opt_info["cy"], f"Reason specified Option {lbl}: '{opt_info['text']}' ({reason})"
                
    # 3. Match option_text against options text
    if opt_text:
        # Exact text match
        for lbl, opt_info in options.items():
            if opt_info["text"] and opt_info["text"].strip().lower() == opt_text:
                return lbl, opt_info["cx"], opt_info["cy"], f"Matched option text '{opt_text}' -> Option {lbl}"
        # Substring text match
        for lbl, opt_info in options.items():
            if opt_info["text"] and (opt_text in opt_info["text"].strip().lower() or opt_info["text"].strip().lower() in opt_text):
                return lbl, opt_info["cx"], opt_info["cy"], f"Matched substring '{opt_info['text']}' -> Option {lbl}"

    # 4. Search reason for any option text
    matched_from_reason = []
    for lbl, opt_info in options.items():
        t = opt_info["text"].strip().lower()
        if t and len(t) > 0 and t in reason_low:
            matched_from_reason.append((lbl, opt_info))
    if len(matched_from_reason) == 1:
        lbl, opt_info = matched_from_reason[0]
        return lbl, opt_info["cx"], opt_info["cy"], f"Option text '{opt_info['text']}' found in explanation -> Option {lbl}"

    return None, None, None, None

def smart_fallback_solve(question, options):
    """
    Heuristic gaming knowledge fallback if Ollama is unreachable.
    Does NOT blindly default to Option A!
    """
    if not question or not options:
        return None, None, None, None
        
    q_low = question.lower()
    
    rules = [
        (["solo", "सोलो"], ["1", "एक", "one"]),
        (["duo", "डुओ"], ["2", "दो", "two"]),
        (["trio", "ट्रायो"], ["3", "तीन", "three"]),
        (["squad", "स्कवाड", "स्क्वाड"], ["4", "चार", "four"]),
        (["headshot", "हेडशॉट", "head shot"], ["head", "सिर", "खोपड़ी"]),
        (["med kit", "medkit", "med-kit", "मेड किट", "मेडकिट", "bandage", "पट्टी"], ["hp", "health", "खून", "स्वास्थ्य", "लाइफ", "life"]),
        (["air drop", "airdrop", "एयरड्रॉप", "एयर ड्रॉप"], ["plane", "प्लेन", "crane", "बॉक्स", "क्रिएट", "crate"]),
        (["danger zone", "red zone", "डेंजर ज़ोन", "रेड ज़ोन"], ["bomb", "बम", "धमाका", "विस्फोट"]),
        (["gloowall", "gloo wall", "ग्लू वॉल", "ग्लूवाल"], ["cover", "कवर", "shield", "दीवार", "बचाव", "सुरक्षा", "defence", "आड़"]),
        (["ammo", "ammunition", "एमो", "गोली", "कारतूस"], ["bullet", "गन", "बंदूक", "फायर"]),
        (["scope", "स्कोप", "दूरबीन"], ["zoom", "ज़ूम", "निशाना", "देखने"]),
        (["revive", "रिवाइव"], ["teammate", "साथी", "बचाने", "उठाने"]),
        (["अच्छा खिलाड़ी", "pro player", "प्रो प्लेयर", "बेहतर खिलाड़ी", "जीतने", "skill", "स्किल्स"], ["practice", "प्रैक्टिस", "अभ्यास", "skill", "मेहनत", "ट्रेनिंग", "focus"]),
        (["rank", "रैंक", "tier", "टियर", "grandmaster", "ग्रैंडमास्टर"], ["push", "point", "पॉइंट", "बढ़ाना", "स्कोर", "प्लस"]),
        (["booyah", "बूयाह", "चिकन डिनर", "chicken dinner"], ["जीत", "win", "लास्ट", "survival", "बचना"]),
        (["loot", "लूट"], ["गन", "weapon", "हथियार", "आर्मर", "वेस्ट", "helmet"]),
        (["zone", "safe zone", "सेफ ज़ोन"], ["shrink", "छोटा", "सर्कल", "circle", "अंदर"]),
    ]
    
    for q_keywords, ans_keywords in rules:
        if any(kw in q_low for kw in q_keywords):
            for lbl, opt in options.items():
                opt_t = opt["text"].lower()
                if any(ak in opt_t for ak in ans_keywords):
                    return lbl, opt["cx"], opt["cy"], f"Rule matched '{q_keywords[0]}' -> Option {lbl} ({opt['text']})"
                    
    return None, None, None, None

def detect_and_handle_common_dialogs(elements):
    """
    Instantly handles common dialogs and error alerts (e.g. 'Connection reset' + 'OK', 'Network error', 'Retry')
    without any delay.
    """
    all_text = " ".join([e.get("text", "").lower() for e in elements])
    
    has_popup = any(kw in all_text for kw in [
        "connection reset", "connection error", "network error", "no internet",
        "please check", "went wrong", "server error", "error", "alert", "notice",
        "warning", "session expired", "try again", "reconnect", "failed", "offline"
    ])
    
    if has_popup:
        for target in ["ok", "okay", "retry", "try again", "dismiss", "got it", "continue", "confirm", "close", "agree"]:
            for el in elements:
                t = (el.get("text") or "").strip().lower()
                if t == target or (len(t) < 15 and target in t and ("button" in el.get("id", "").lower() or el.get("clickable", False))):
                    cx = el.get("cx") if "cx" in el else el.get("bounds", {}).get("cx", 540)
                    cy = el.get("cy") if "cy" in el else el.get("bounds", {}).get("cy", 1200)
                    print(f"\n⚡ [FAST DIALOG RESOLVER] Detected popup dialog ('{has_popup}') -> Clicking '{el.get('text')}' at ({cx}, {cy})", flush=True)
                    tap(cx, cy)
                    time.sleep(2)
                    return True
    return False

def ask_ollama_general_event(elements, config):
    """
    Asks Ollama (llama3.2) to autonomously analyze unknown events, popups, dialogs, 
    and calculate where to click to resolve them and keep tasks running in all conditions.
    """
    host = config.get("ollama_host", "http://127.0.0.1:11434").replace("localhost", "127.0.0.1")
    model = config.get("ollama_model", "llama3.2:latest")
    
    texts = [e.get("text", "").strip() for e in elements if e.get("text") and len(e.get("text").strip()) > 1]
    unique_texts = []
    seen = set()
    for t in texts:
        if t not in seen:
            seen.add(t)
            unique_texts.append(t)
            
    candidates = []
    for e in elements:
        t = (e.get("text") or "").strip()
        if t and len(t) < 40 and not any(w in t.lower() for w in ["wait", "sec", "loading"]):
            cx = e.get("cx") if "cx" in e else e.get("bounds", {}).get("cx", 540)
            cy = e.get("cy") if "cy" in e else e.get("bounds", {}).get("cy", 1200)
            candidates.append({
                "index": len(candidates) + 1,
                "text": t,
                "cx": cx,
                "cy": cy
            })
            
    if not candidates:
        return None, []
        
    cand_str = "\n".join([f"[{c['index']}] '{c['text']}' at pixel ({c['cx']}, {c['cy']})" for c in candidates[:15]])
    screen_summary = "\n".join([f"- {t}" for t in unique_texts[:10]])
    
    prompt = f"""You are an autonomous Android bot controller.
The phone screen currently displays an event, popup, dialog, or UI state that needs to be handled.

Screen Context:
{screen_summary}

Interactive Elements on Screen:
{cand_str}

Goal:
1. If there is an error, dialog, or popup like 'Connection reset', network error, alert, or notice, select 'OK', 'Retry', or 'Dismiss' to clear it.
2. If there is a reward, bonus, collect, continue, or start button, select it to proceed.
3. Determine the best button to click, its index, and reason.

Return JSON strictly:
{{"action": "CLICK", "target_index": <number 1-{len(candidates)}>, "target_text": "<text of button>", "reason": "<short explanation>"}}
Or if waiting or pressing back is better:
{{"action": "BACK" or "WAIT", "reason": "<short explanation>"}}
"""
    payload = {
        "model": model,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "keep_alive": -1,
        "options": {
            "temperature": 0.0,
            "num_predict": 120
        }
    }
    
    url = f"{host}/api/generate"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ans_str = data.get("response", "").strip()
            parsed = parse_ollama_json(ans_str)
            return parsed, candidates
    except Exception as e:
        print(f"⚠️ [Ollama Event Error] {e}", flush=True)
    return None, candidates

def run_loop():
    config = load_config()
    interval = config.get("interval_seconds", 1.0)
    
    dev = select_device(config.get("device_id"))
    if not dev:
        print("❌ No mobile device detected via ADB! Please connect your phone with USB debugging enabled.", flush=True)
        notify_error("No mobile device detected via ADB.")
        return
        
    print("\n" + "=" * 65)
    print("🚀 TEXT-BASED AI MOBILE AUTO-TASK BOT (LOCAL OLLAMA ENGINE)")
    print(f"📱 Target Device: {dev}")
    print(f"🦙 Ollama Model: {config.get('ollama_model', 'llama3.2:latest')}")
    print(f"⏱️  Loop Interval: {interval}s")
    print("=" * 65 + "\n")
    
    # Preload and warm up Ollama model into GPU/RAM so it never times out on Cycle #1
    warmup_ollama(config)
    
    ensure_screen_awake()
    
    cycle = 0
    last_limit_prompt_time = 0
    stall_count = 0  # Track consecutive Add Bonus taps without counter advance
    justTappedBonus = False  # Flag: Add Bonus was just tapped, ad may be playing
    last_counter = None  # Track last seen counter value
    while True:
        cycle += 1
        print(f"\n--- [Cycle #{cycle} | {time.strftime('%H:%M:%S')}] Reading screen hierarchy... ---", flush=True)
        
        # Check if background uninstallation of in.binarybox is due on the 2nd loop
        check_pending_uninstall()

        # 1. Get screen UI hierarchy without photo
        elements = get_screen_ui()
        if not elements:
            print("⚠️  No text found on screen (phone locked, screen off, or empty canvas). Waking screen...", flush=True)
            ensure_screen_awake()
            time.sleep(interval)
            continue
            
        all_text = " ".join([e.get("text", "").lower() for e in elements])
        counter = extract_task_counter(elements)

        # --- STALL DETECTION: Check if counter hasn't advanced ---
        if counter and last_counter and counter == last_counter:
            stall_count += 1
            if stall_count >= 3:
                print(f"🚨 [STALL DETECTED] Counter stuck at {counter} for {stall_count} cycles! Triggering AI vision analyzer...", flush=True)
                try:
                    import winsound
                    for _ in range(3):
                        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                        time.sleep(0.3)
                except Exception:
                    pass
                QUIZ_STATE["last_quiz_id"] = None
                QUIZ_STATE["repeat_count"] = 0
        else:
            stall_count = 0
        last_counter = counter
        # --- END STALL DETECTION ---

        # --- BYPASS LOOP DETECTION ---
        if QUIZ_STATE.get("bypass_loop_detected"):
            print(f"🚨 [BYPASS LOOP] Using AI vision analyzer to resolve stuck counter at {counter}...", flush=True)
            QUIZ_STATE["bypass_loop_detected"] = False
            QUIZ_STATE["last_quiz_id"] = None
        # --- END BYPASS LOOP DETECTION ---
        
        # Check Done / Daily Limit
        if "limit over" in all_text or "daily limit" in all_text or "task completed" in all_text:
            now = time.time()
            if now - last_limit_prompt_time > 30: # 30s cooldown after choosing Continue
                print("🏁 [ALERT] Daily Limit reached or task completed on screen!", flush=True)
                auto_cont = config.get("auto_continue_on_limit", False) or config.get("auto_continue", False)
                should_continue = prompt_task_complete(
                    "Daily limit reached or current task completed!",
                    auto_continue=auto_cont
                )
                if should_continue:
                    last_limit_prompt_time = time.time()
                    print("⏩ [CONTINUING] Bot will stay active so other tasks can complete.", flush=True)
                    print("📱 You have 5 seconds to switch to the next task on your phone...", flush=True)
                    time.sleep(5)
                    continue
                else:
                    print("🏁 Stopping script as requested by user.", flush=True)
                    break
            else:
                # Within cooldown, ignore repeated limit triggers while navigating
                pass
            
        # 2. Check Add Bonus / Claim popup FIRST
        bonus_handled = False
        for el in elements:
            t = el["text"].strip().lower()
            if "add bonus" in t or t == "add" or "claim" in t or "collect" in t:
                print(f"🎁 [BONUS] Found '{el['text']}' button -> Tapping ({el['cx']}, {el['cy']})", flush=True)
                stall_count += 1
                tap(el["cx"], el["cy"])
                bonus_handled = True
                justTappedBonus = True  # Mark that we just tapped Add Bonus
                time.sleep(2)
                if stall_count >= 3:
                    print("ALERT [STALL] Too many Add Bonus taps without progress. Falling through to AI vision analyzer...", flush=True)
                    bonus_handled = False
                    break
                break
        if bonus_handled:
            # Don't clear justTappedBonus yet - ad may still be playing
            continue

        # 2.6 Check for Install Task during ad (after Add Bonus tapped)
        if justTappedBonus:
            # Check if there's a video/watch/install task on screen
            for el in elements:
                t = (el.get("text") or "").strip().lower()
                # Detect video ad / watch task / install app task
                if any(kw in t for kw in ["play video", "final watch", "watch video", "install", "open", "play"]):
                    print(f"? [INSTALL TASK] Detected install task during ad: {el['text']} -> Running install bypass before closing ad...", flush=True)
                    justTappedBonus = False
                    perform_fake_install_bypass()
                    continue
            # No install task found - clear flag and let ad close happen normally
            justTappedBonus = False

        # 2.5 Check Popup Dialogs (Connection reset, error, alert, etc.)
        if detect_and_handle_common_dialogs(elements):
            continue
            
        # 3. Check Ad Close / Skip
        ad_handled = False
        for el in elements:
            t = el["text"].strip().lower()
            if t in ["close", "close ad", "skip", "dismiss"] or (el.get("clickable") and "close" in t):
                print(f"❌ [CLOSE AD] Found '{el['text']}' button -> Tapping ({el['cx']}, {el['cy']})", flush=True)
                tap(el["cx"], el["cy"])
                ad_handled = True
                time.sleep(1.5)
                break
        if ad_handled:
            justTappedBonus = False  # Ad closed, clear flag
            continue
            
        # 4. Check Timer (e.g. 'Wait 7 sec...')
        timer_found = False
        for el in elements:
            t = el["text"].strip().lower()
            if "wait" in t and "sec" in t:
                print(f"⏳ [TIMER] Waiting for timer: '{el['text']}'", flush=True)
                timer_found = True
                time.sleep(2.5)
                break
        if timer_found:
            continue
            
        # 5. Check Final Watch / Play Video button
        final_watch_handled = False
        for el in elements:
            t = el["text"].strip().lower()
            if "final watch" in t:
                print(f"🎬 [FINAL WATCH] Found '{el['text']}' button -> Tapping ({el['cx']}, {el['cy']})", flush=True)
                tap(el["cx"], el["cy"])
                print("⏳ [FINAL WATCH] Waiting 5 seconds before going to Home screen...", flush=True)
                time.sleep(5)
                print("🚀 [FINAL WATCH BYPASS] Proceeding to install application task...", flush=True)
                perform_fake_install_bypass()
                final_watch_handled = True
                break
        if final_watch_handled:
            continue

        video_handled = False
        for el in elements:
            t = el["text"].strip().lower()
            if "play video" in t or t == "play":
                print(f"🎬 [VIDEO] Found '{el['text']}' button -> Tapping ({el['cx']}, {el['cy']})", flush=True)
                tap(el["cx"], el["cy"])
                video_handled = True
                time.sleep(2)
                break
        if video_handled:
            continue
            
        # 6. Check Quiz Screen & 3-Loop Repetition Tracking (e.g. 9/20 stuck)
        question, options = extract_quiz_info(elements)
        quiz_key = counter if counter else question
        
        if quiz_key and ((question and options and len(options) >= 2) or counter):
            if QUIZ_STATE["last_quiz_id"] == quiz_key:
                QUIZ_STATE["repeat_count"] += 1
                print(f"🔁 [QUIZ REPEAT] Task '{quiz_key}' repeated ({QUIZ_STATE['repeat_count']}/3 loops)", flush=True)
            else:
                QUIZ_STATE["last_quiz_id"] = quiz_key
                QUIZ_STATE["repeat_count"] = 1
                print(f"📊 [QUIZ TASK] Active Quiz task: '{quiz_key}' (Loop 1/3)", flush=True)

            if QUIZ_STATE["repeat_count"] >= 3:
                print(f"\n🚀 [TRIGGER BYPASS] Quiz task '{quiz_key}' repeated 3 times in 3 loops!", flush=True)
                QUIZ_STATE["bypass_tracker"] = counter  # Remember which counter triggered bypass
                perform_fake_install_bypass()
                continue
                
        if question and options and len(options) >= 2:
            print(f"❓ [QUIZ DETECTED] Question: '{question}'", flush=True)
            opts_summary = ", ".join([f"{k}: '{v['text']}'" for k, v in sorted(options.items())])
            print(f"📋 Options: {opts_summary}", flush=True)
            
            # Query Ollama
            print(f"🦙 Asking local Ollama ({config.get('ollama_model', 'llama3.2:latest')})...", flush=True)
            decision = ask_ollama_quiz(question, options, config)
            print(f"💡 Ollama Raw Decision: {decision}", flush=True)
            
            # Resolve correct coordinates from Ollama response
            lbl, cx, cy, reason = resolve_option_click(decision, options)
            
            # Fallback if Ollama did not answer
            if not lbl:
                if config.get("gemini_api_key"):
                    print("🌐 Ollama unavailable or timed out. Trying Gemini Cloud AI fallback...", flush=True)
                    gem_decision = ask_gemini_quiz(question, options, config)
                    if gem_decision:
                        lbl, cx, cy, reason = resolve_option_click(gem_decision, options)
                        if lbl:
                            print(f"💡 Gemini Raw Decision: {gem_decision}", flush=True)
            if not lbl:
                print("⚡ Using Smart Gaming Rules fallback...", flush=True)
                lbl, cx, cy, reason = smart_fallback_solve(question, options)
                
            if lbl and cx and cy:
                print(f"🎯 [QUIZ ANSWER] Selected Option {lbl} ('{options[lbl]['text']}') -> Tapping exact pixel ({cx}, {cy})", flush=True)
                print(f"📝 Reason: {reason}", flush=True)
                tap(cx, cy)
                time.sleep(2.0)
            else:
                print("⚠️ Could not confidently resolve correct option. Waiting for next cycle...", flush=True)
                time.sleep(interval)
            continue
            
        # 7. Check Start Quiz banner on Home
        start_quiz_handled = False
        for el in elements:
            t = el["text"].strip().lower()
            if "daily gaming quiz" in t or "gaming quiz" in t:
                print(f"🎮 [START QUIZ] Tapping '{el['text']}' at ({el['cx']}, {el['cy']})", flush=True)
                tap(el["cx"], el["cy"])
                start_quiz_handled = True
                time.sleep(2)
                break
        if start_quiz_handled:
            continue
            
        # 8. Autonomous Ollama Screen & Event Analyzer (Handles unknown popups, connection resets, dialogs in all conditions)
        print("🤖 [AI ANALYZER] Asking Ollama to analyze screen event and calculate action...", flush=True)
        ollama_decision, candidates = ask_ollama_general_event(elements, config)
        if ollama_decision:
            action = str(ollama_decision.get("action", "")).upper()
            target_idx = ollama_decision.get("target_index")
            target_text = str(ollama_decision.get("target_text") or "").strip().lower()
            reason = ollama_decision.get("reason", "")
            
            if action == "CLICK":
                click_x, click_y = None, None
                # Match by index
                if target_idx and isinstance(target_idx, int) and 1 <= target_idx <= len(candidates):
                    c = candidates[target_idx - 1]
                    click_x, click_y = c["cx"], c["cy"]
                    print(f"🎯 [OLLAMA DECISION] Selected Option #{target_idx} ('{c['text']}') -> Calculated Pixel ({click_x}, {click_y})", flush=True)
                # Match by text
                elif target_text:
                    for el in elements:
                        t = (el.get("text") or "").strip().lower()
                        if t and (target_text == t or target_text in t):
                            click_x = el.get("cx") if "cx" in el else el.get("bounds", {}).get("cx")
                            click_y = el.get("cy") if "cy" in el else el.get("bounds", {}).get("cy")
                            print(f"🎯 [OLLAMA DECISION] Matched text '{el['text']}' -> Calculated Pixel ({click_x}, {click_y})", flush=True)
                            break
                            
                if click_x and click_y:
                    print(f"👉 [OLLAMA ACTION] Tapping ({click_x}, {click_y}) | Reason: {reason}", flush=True)
                    tap(click_x, click_y)
                    time.sleep(2)
                    continue
            elif action == "BACK":
                print(f"🔙 [OLLAMA ACTION] Pressing Back | Reason: {reason}", flush=True)
                send_back()
                time.sleep(1.5)
                continue
                
        print("⏳ No immediate action needed. Waiting for next cycle...", flush=True)
        time.sleep(interval)

if __name__ == "__main__":
    register_exit_sound()
    if len(sys.argv) > 1 and sys.argv[1].lower() in ["bypass-install", "install-bypass", "install"]:
        perform_fake_install_bypass()
    else:
        try:
            run_loop()
        except KeyboardInterrupt:
            print("\n👋 Bot stopped by user (Ctrl+C). Exiting safely.", flush=True)
            notify_script_stopped("Bot stopped by user.")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}", flush=True)
            notify_error(f"Fatal error: {e}")
            raise
