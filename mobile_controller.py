import os
import sys
import time
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import urllib.request
import urllib.parse

from sound_notifier import (
    play_sound,
    notify_task_complete,
    notify_script_stopped,
    notify_error,
    register_exit_sound
)

# Force UTF-8 output on Windows console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Find ADB executable
ADB_CANDIDATES = [
    r"C:\Users\tejas\AppData\Local\Android\Sdk\platform-tools\adb.exe",
    r"D:\mirzapur\scrcpy-win64-v3.2\platform-tools\adb.exe",
    r"C:\Users\tejas\Desktop\platform-tools\adb.exe",
    "adb"
]

def get_adb_path():
    for p in ADB_CANDIDATES:
        if os.path.exists(p):
            return p
    return "adb"

ADB = get_adb_path()
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mobile_config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "triggerKeywords": ["?", "quiz", "Question"],
        "actionButtons": ["Submit", "Add", "Next", "Continue"],
        "pollIntervalSeconds": 1.0,
        "autoAnswerQuiz": True,
        "optionsPrefixes": ["A", "B", "C", "D"]
    }

def run_adb(args, capture_output=True, binary=False):
    cmd = [ADB] + args
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE if capture_output else None,
                             stderr=subprocess.PIPE if capture_output else None)
        if binary:
            return res.stdout
        return res.stdout.decode("utf-8", errors="replace").strip()
    except Exception as e:
        print(f"[ADB Error] {e}")
        return "" if not binary else b""

def check_device():
    out = run_adb(["devices"])
    lines = [line.strip() for line in out.splitlines() if line.strip() and not line.startswith("*")]
    device_lines = [l for l in lines if not l.startswith("List of")]
    if not device_lines:
        print("[!] No mobile device detected. Please connect phone via USB or Wi-Fi.")
        return False, "disconnected"
    for l in device_lines:
        parts = l.split()
        serial = parts[0]
        state = parts[1] if len(parts) > 1 else "unknown"
        if state == "unauthorized":
            print(f"[!] Device {serial} is UNAUTHORIZED.")
            print("[ACTION NEEDED]: Look at your phone screen and tap 'ALLOW' on the 'Allow USB debugging?' popup!")
            return False, "unauthorized"
        elif state == "device":
            print(f"[CONNECTED] Mobile device '{serial}' is connected and ready!")
            return True, serial
    print(f"[!] Device state: {device_lines}")
    return False, "unknown"

def capture_mobile_screenshot(save_name="mobile_screen.png"):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    save_path = os.path.join(script_dir, save_name)
    run_adb(["shell", "screencap", "-p", "/sdcard/screen.png"])
    run_adb(["pull", "/sdcard/screen.png", save_path])
    print(f"[OK] Mobile screenshot saved to: {save_path}")
    return save_path

def parse_bounds(bounds_str):
    # bounds="[startX,startY][endX,endY]"
    m = re.findall(r"\[(\d+),(\d+)\]", bounds_str)
    if len(m) == 2:
        x1, y1 = int(m[0][0]), int(m[0][1])
        x2, y2 = int(m[1][0]), int(m[1][1])
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        return {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "cx": cx, "cy": cy}
    return None

def get_screen_elements():
    # Fast UI Automator dump
    run_adb(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"])
    xml_data = run_adb(["shell", "cat", "/sdcard/window_dump.xml"])
    if not xml_data or "<hierarchy" not in xml_data:
        return []
    
    elements = []
    try:
        # Extract from XML
        root = ET.fromstring(xml_data[xml_data.find("<hierarchy"):])
        for node in root.iter("node"):
            text = node.attrib.get("text", "").strip()
            desc = node.attrib.get("content-desc", "").strip()
            bounds_str = node.attrib.get("bounds", "")
            clickable = node.attrib.get("clickable", "false") == "true"
            
            content = text if text else desc
            if content and bounds_str:
                b = parse_bounds(bounds_str)
                if b:
                    elements.append({
                        "text": content,
                        "resource_id": node.attrib.get("resource-id", ""),
                        "class": node.attrib.get("class", ""),
                        "clickable": clickable,
                        "bounds": b
                    })
    except Exception as e:
        print(f"[XML Parse Error] {e}")
    return elements

def tap(x, y):
    print(f"[TAP] Tapping on phone at ({x}, {y})")
    run_adb(["shell", "input", "tap", str(x), str(y)])

def click_text(target_text, exact=False):
    elements = get_screen_elements()
    target_lower = target_text.lower().strip()
    for el in elements:
        t = el["text"].strip()
        matched = (t.lower() == target_lower) if exact else (target_lower in t.lower())
        if matched:
            b = el["bounds"]
            print(f"[CLICK-TEXT] Found '{t}' -> Clicking center ({b['cx']}, {b['cy']})")
            tap(b["cx"], b["cy"])
            return True
    print(f"[!] Text '{target_text}' not found on phone screen.")
    return False

def extract_quiz_and_options(elements):
    question_candidates = []
    option_letters = []
    text_items = []

    for el in elements:
        t = el["text"].strip()
        if not t:
            continue
        if "?" in t or "कहा जाता" in t or "किसे कहते" in t:
            question_candidates.append(t)
        elif re.match(r"^[A-Da-d]\.?$", t):
            option_letters.append(el)
        else:
            text_items.append(el)

    if not question_candidates:
        return None, []

    question = " ".join(question_candidates)
    
    # Pair each option letter with text on the same Y row (within 60px)
    paired_options = []
    for letter_el in option_letters:
        ly = letter_el["bounds"]["cy"]
        best_match = None
        min_dy = 999
        for txt_el in text_items:
            dy = abs(txt_el["bounds"]["cy"] - ly)
            if dy < 60 and dy < min_dy:
                min_dy = dy
                best_match = txt_el
        
        full_text = f"{letter_el['text']} {best_match['text']}" if best_match else letter_el['text']
        click_target = best_match if best_match else letter_el
        paired_options.append({
            "letter": letter_el["text"],
            "text": full_text,
            "answer_text": best_match["text"] if best_match else "",
            "bounds": click_target["bounds"]
        })

    return question, paired_options

def search_web_for_answer(question, options):
    print(f"\n[AI-SEARCH] Solving Question: \"{question}\"")
    try:
        # Gaming heuristics for common Hindi gaming questions:
        q_lower = question.lower()
        if "solo" in q_lower and ("team" in q_lower or "खिलाड़ी" in q_lower):
            for opt in options:
                if "1" in opt["text"]:
                    return opt
        if "duo" in q_lower and ("team" in q_lower or "खिलाड़ी" in q_lower):
            for opt in options:
                if "2" in opt["text"]:
                    return opt
        if "squad" in q_lower and ("team" in q_lower or "खिलाड़ी" in q_lower):
            for opt in options:
                if "4" in opt["text"]:
                    return opt
        if "headshot" in q_lower:
            for opt in options:
                if "सिर" in opt["text"] or "head" in opt["text"].lower():
                    return opt

        # Web search with DuckDuckGo
        query = urllib.parse.quote(question)
        url = f"https://html.duckduckgo.com/html/?q={query}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=4) as response:
            html = response.read().decode('utf-8', errors='ignore').lower()

        scores = {}
        for opt in options:
            ans_clean = opt["answer_text"].strip().lower()
            if len(ans_clean) >= 1:
                count = html.count(ans_clean)
                scores[opt["letter"]] = count
            else:
                scores[opt["letter"]] = 0

        print(f"[SEARCH SCORES] {scores}")
        if scores:
            best_letter = max(scores, key=scores.get)
            if scores[best_letter] > 0:
                for opt in options:
                    if opt["letter"] == best_letter:
                        return opt
    except Exception as e:
        print(f"[Search Warning] {e}")

    return options[0] if options else None

def solve_current_quiz(elements, config):
    question, options = extract_quiz_and_options(elements)
    if question and options:
        print(f"\n[QUIZ DETECTED]")
        print(f" Question: {question}")
        for opt in options:
            print(f"  {opt['text']} -> center: ({opt['bounds']['cx']}, {opt['bounds']['cy']})")

        winning_opt = search_web_for_answer(question, options)
        if winning_opt:
            b = winning_opt["bounds"]
            print(f"\n[CLICKING ANSWER] Selecting '{winning_opt['text']}' at ({b['cx']}, {b['cy']})")
            tap(b["cx"], b["cy"])
            return True
    return False

def handle_popups_and_ads(elements):
    # Check for Ad close button (e.g. "Close", "Close Ad", "close")
    for el in elements:
        t = el["text"].strip().lower()
        if t in ["close", "close ad", "skip", "dismiss"] or (el.get("clickable") and "close" in t):
            b = el["bounds"]
            print(f"[AD CLOSE] Clicking Close Ad at ({b['cx']}, {b['cy']})", flush=True)
            tap(b["cx"], b["cy"])
            return True

    # Check for interstitial Ad elements (e.g. Install, Ad 1 of 2)
    for el in elements:
        t = el["text"].strip().lower()
        if "ad 1 of" in t or "install now" in t or "open google play" in t:
            print("[AD PLAYING] Detected Ad... Waiting 5s then tapping close / Back", flush=True)
            time.sleep(5)
            # Try top-right close area or Back button
            tap(1013, 176)
            time.sleep(1)
            run_adb(["shell", "input", "keyevent", "4"])
            return True

    # Check for "Add Bonus" button
    for el in elements:
        t = el["text"].strip().lower()
        if "add bonus" in t or t == "add":
            b = el["bounds"]
            print(f"[BONUS] Found 'Add Bonus' button -> Clicking ({b['cx']}, {b['cy']})", flush=True)
            tap(b["cx"], b["cy"])
            return True

    # Check for "Wait ... sec" timer
    for el in elements:
        t = el["text"].strip().lower()
        if "wait" in t and "sec" in t:
            print(f"[TIMER] Waiting for timer: {el['text']}", flush=True)
            time.sleep(2)
            return True

    return False

def see_mobile_screen():
    ok, status = check_device()
    if not ok:
        return
    
    # 1. Take screenshot
    shot_path = capture_mobile_screenshot("mobile_screen.png")
    
    # 2. Dump UI elements
    elements = get_screen_elements()
    print(f"\n=== WHAT IS ON YOUR MOBILE SCREEN ({len(elements)} elements found) ===")
    for idx, el in enumerate(elements, 1):
        b = el["bounds"]
        click_tag = "[CLICKABLE]" if el["clickable"] else ""
        print(f"{idx:2d}. \"{el['text']}\" {click_tag} -> Center: ({b['cx']}, {b['cy']})")

def watch_and_automate():
    ok, status = check_device()
    if not ok:
        return
    
    config = load_config()
    interval = config.get("pollIntervalSeconds", 1.0)
    print(f"[WATCHER STARTED] Polling mobile screen every {interval}s... Press Ctrl+C to stop.")
    
    last_action_time = 0
    while True:
        try:
            elements = get_screen_elements()
            if not elements:
                time.sleep(interval)
                continue
            
            acted = False
            # Check 1: Popups, Ads, "Add Bonus", and Timers
            if handle_popups_and_ads(elements):
                acted = True
                time.sleep(1.0)
            
            # Check 2: Quiz Auto-Solver
            elif config.get("autoAnswerQuiz", True):
                if solve_current_quiz(elements, config):
                    acted = True
                    time.sleep(2.0)
            
            # Check 3: Home screen "Daily Gaming Quiz" banner
            elif not acted:
                for el in elements:
                    if "Daily" in el["text"] and "Bonus" in el["text"]:
                        # We are on home screen! Tap Daily Gaming Quiz banner
                        print("[HOME SCREEN] Detected Home -> Entering Daily Gaming Quiz")
                        tap(540, 550)
                        time.sleep(2.0)
                        break
            
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[STOPPED] Watcher stopped by user.")
            notify_script_stopped("Watcher stopped by user.")
            break
        except Exception as e:
            print(f"[Error in loop] {e}")
            time.sleep(interval)

def manual_watch():
    """Continuously dump mobile UI XML and prompt user for manual actions."""
    ok, status = check_device()
    if not ok:
        return
    
    interval = 2.0  # seconds between polls
    print("[MANUAL WATCH MODE] Continuous XML dump - enter action number or 'q' to quit")
    print("[Ads will be highlighted - enter 'c' to close, 's' to skip, or number to click]")
    
    try:
        while True:
            elements = get_screen_elements()
            if not elements:
                print(f"\n[{time.strftime('%H:%M:%S')}] No XML data received, retrying...")
                time.sleep(interval)
                continue
            
            # Display all elements with ads highlighted
            print(f"\n[{time.strftime('%H:%M:%S')}] {len(elements)} elements on screen:")
            for idx, el in enumerate(elements, 1):
                b = el["bounds"]
                text = el["text"]
                clickable = el["clickable"]
                
                # Highlight ads/buttons
                is_ad = False
                t_lower = text.lower() if text else ""
                if any(kw in t_lower for kw in ["ad", "close", "skip", "install", "bonus"]):
                    is_ad = True
                
                tag = "[AD] " if is_ad else ""
                click_tag = "[CLICK]" if clickable else ""
                print(f"  {idx:2d}. {tag}{click_tag}\"{text}\" at ({b['cx']}, {b['cy']})")
            
            # Prompt for action
            action = input("\nAction (number to tap, 'c'=close ad, 's'=skip, 'q'=quit): ").strip().lower()
            
            if action == 'q':
                print("[EXITING] Manual watch mode stopped.")
                break
            elif action == 's':
                print("[SKIP] Skipping this iteration.")
                continue
            elif action == 'c':
                # Close ad - try finding close button
                for el in elements:
                    t = el["text"].strip().lower()
                    if t in ["close", "close ad", "skip", "dismiss"]:
                        b = el["bounds"]
                        print(f"[CLOSE AD] Tapping close at ({b['cx']}, {b['cy']})")
                        tap(b["cx"], b["cy"])
                        break
                else:
                    print("[NO CLOSE BUTTON Found] No ad close button detected.")
            elif action and action.isdigit():
                idx = int(action)
                if 1 <= idx <= len(elements):
                    el = elements[idx - 1]
                    b = el["bounds"]
                    text = el["text"]
                    print(f"[TAP] Tapping element {idx}: \"{text}\" at ({b['cx']}, {b['cy']})")
                    tap(b["cx"], b["cy"])
                else:
                    print(f"[ERROR] Invalid element number. Choose 1-{len(elements)}")
            else:
                print("[UNKNOWN] Unknown action. Try: number, c, s, or q.")
            
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[STOPPED] Manual watch mode stopped by user.")
    except Exception as e:
        print(f"[Error] {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python mobile_controller.py status             # Check mobile USB connection")
        print("  python mobile_controller.py see                # Capture screen & list all visible text/buttons")
        print("  python mobile_controller.py click <x> <y>      # Tap coordinates on phone")
        print("  python mobile_controller.py click-text <text>  # Find text on phone and tap it")
        print("  python mobile_controller.py run                # Start auto watcher (Quiz solver + Buttons)")
        print("  python mobile_controller.py manual             # Manual watch mode: continuously dump XML and prompt for actions")
        sys.exit(0)
    
    cmd = sys.argv[1].lower()
    if cmd == "status":
        check_device()
    elif cmd == "see":
        see_mobile_screen()
    elif cmd == "click" and len(sys.argv) >= 4:
        tap(sys.argv[2], sys.argv[3])
    elif cmd == "click-text" and len(sys.argv) >= 3:
        click_text(" ".join(sys.argv[2:]))
    elif cmd == "run":
        register_exit_sound()
        watch_and_automate()
    elif cmd == "manual":
        manual_watch()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(0)