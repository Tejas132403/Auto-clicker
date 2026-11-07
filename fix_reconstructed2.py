with open('free_ai_bot_reconstructed.py', 'r', encoding='utf-8') as f:
    text = f.read()

# The problem: f-strings with e['text'] or eb.get('cx', 0) use backslash escapes
# which are invalid inside f-string expressions in Python < 3.12.
# But we're on Python 3.14 which allows it... wait, the error says "unexpected 
# character after line continuation character" - this means \' is being interpreted
# as a line continuation, not an escaped quote.
#
# The issue is the file encoding: when I write \\' to the file, it becomes \' 
# in the actual file content. But in the f-string expression context, \' is a 
# line continuation character followed by a quote, which is a syntax error.
#
# Solution: Write the file with actual single quotes inside f-string expressions.
# In Python 3.12+, you CAN use the same quote type inside f-string expressions.
# So f"{e['text']}" is valid in Python 3.12+.
#
# The problem is how I'm generating the text. When I write:
#   f.write("print(f\"...{e['text']}...\")")
# The \\' in the Python string becomes \' in the output file, which is wrong.
# I need to write actual ' characters.

# Let me rewrite the problematic sections entirely.

# Actually, the simplest fix: replace all f-string dict accesses with 
# pre-extracted variables. No dict access inside f-strings at all.

# Find the problematic function sections and replace them

# Replace perform_fake_install_bypass section
old_pfb_start = text.find('def perform_fake_install_bypass():')
old_pfb_end = text.find('\ndef dismiss_ad_if_present', old_pfb_start)

if old_pfb_start >= 0 and old_pfb_end >= 0:
    new_pfb = '''def perform_fake_install_bypass():
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
    print("\\n\\U0001f4e6 ====================================================", flush=True)
    print("\\U0001f680 [INSTALL BYPASS] Triggered: Bypassing Ad Installation!", flush=True)
    print("\\U0001f4e6 ====================================================", flush=True)

    app_pkg = get_current_app_package()
    if app_pkg:
        QUIZ_STATE["target_app_package"] = app_pkg
    target_app = QUIZ_STATE.get("target_app_package", "com.shake.master")

    # Step 1: Go to phone Home screen
    print("\\U0001f3e0 [STEP 1] Going to phone Home Screen...", flush=True)
    run_adb(["shell", "input", "keyevent", "3"])
    time.sleep(1.5)

    # Step 2: Install APK via ADB
    bname = os.path.basename(DUMMY_APK_PATH)
    print(f"? [STEP 2] Installing \\'{bname}\\'...", flush=True)
    if os.path.exists(DUMMY_APK_PATH):
        run_adb(["uninstall", DUMMY_PACKAGE])
        res = run_adb(["install", "-r", "-g", DUMMY_APK_PATH])
        print(f"   Install Status: {res}", flush=True)
    else:
        print(f"?? APK file not found at: {DUMMY_APK_PATH}", flush=True)

    # Step 3: Open for 5 seconds
    print(f"?? [STEP 3] Opening {DUMMY_PACKAGE} for 5 seconds...", flush=True)
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
    print(f"? [STEP 4] Switching back to our app ({target_app})...", flush=True)
    run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])
    time.sleep(2.5)

    # [VERIFY] Confirm we are back in target app
    _back_pkg = get_current_app_package()
    if _back_pkg != target_app:
        pkg_info = f"got \\'{_back_pkg}\\' not \\'{target_app}\\'"
        print(f"? [BYPASS VERIFY] Return failed ({pkg_info}). Force-launching...", flush=True)
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
        et = e.get("text", "") or ""
        t = et.strip().lower()
        if "add bonus" in t or t == "add" or "claim" in t or "collect" in t:
            eb = e.get("bounds", {})
            cx = eb.get("cx", 0)
            cy = eb.get("cy", 0)
            print(f"\\U0001f3e1 Found \\'{et}\\' button -> Tapping ({cx}, {cy})", flush=True)
            tap(cx, cy)
            clicked_action = True
            time.sleep(1.5)
            break

    # Check if a close / dialog button is visible instead
    if not clicked_action:
        for e in elements:
            et = e.get("text", "") or ""
            t = et.strip().lower()
            clickable = e.get("clickable")
            if t in ["close", "skip", "dismiss", "ok", "cancel"] or (clickable and "close" in t):
                eb = e.get("bounds", {})
                cx = eb.get("cx", 0)
                cy = eb.get("cy", 0)
                print(f"\\u26a1 Found dialog button \\'{et}\\' -> Tapping ({cx}, {cy})", flush=True)
                tap(cx, cy)
                clicked_action = True
                time.sleep(1)
                break

    if not clicked_action:
        print("\\u2139 No \\'Add Bonus\\' popup detected. Proceeding to main bot loop to decide according to screen.", flush=True)
    time.sleep(1)

    # Step 6: Schedule deletion in 2nd loop in background
    QUIZ_STATE["pending_uninstall_loops"] = 2
    QUIZ_STATE["repeat_count"] = 0
    QUIZ_STATE["last_quiz_id"] = None
    print("\\u2787 [STEP 6] Scheduled deletion of in.binarybox in 2nd loop in background.", flush=True)
    print("\\u2705 [INSTALL BYPASS COMPLETE] Continuing bot task without interruption!\\n", flush=True)
    return True

'''
    text = text[:old_pfb_start] + new_pfb + text[old_pfb_end:]
    print('Replaced perform_fake_install_bypass')

# Replace dismiss_ad_if_present
old_dismiss_start = text.find('def dismiss_ad_if_present():')
old_dismiss_end = text.find('\ndef handle_add_bonus_and_wait', old_dismiss_start)

if old_dismiss_start >= 0 and old_dismiss_end >= 0:
    new_dismiss = '''def dismiss_ad_if_present():
    """Dismisses top-right close \\'X\\' or dialog close if an ad popup is showing."""
    elements = get_ui_elements()
    for e in elements:
        et = (e.get("text") or "") or ""
        t = et.strip().lower()
        clickable = e.get("clickable")
        if t in ["close", "close ad", "skip", "dismiss"] or (clickable and "close" in t):
            eb = e.get("bounds", {})
            cx = eb.get("cx", 0)
            cy = eb.get("cy", 0)
            print(f"\\u274c Found ad close button \\'{et}\\' -> Tapping ({cx}, {cy})", flush=True)
            tap(cx, cy)
            return True
    # Fallback: tap common top-right close area
    print("\\u274c Tapping common top-right ad cross area (1013, 176)...", flush=True)
    tap(1013, 176)
    return False

'''
    text = text[:old_dismiss_start] + new_dismiss + text[old_dismiss_end:]
    print('Replaced dismiss_ad_if_present')

# Replace handle_add_bonus_and_wait
old_hab_start = text.find('def handle_add_bonus_and_wait():')
old_hab_end = text.find('\ndef handle_play_video_and_wait', old_hab_start)

if old_hab_start >= 0 and old_hab_end >= 0:
    new_hab = '''def handle_add_bonus_and_wait():
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
        et = (e.get("text") or "") or ""
        t = et.strip().lower()
        if "add bonus" in t or t == "add":
            eb = e.get("bounds", {})
            cx = eb.get("cx", 0)
            cy = eb.get("cy", 0)
            print(f"\\u2192 Found \\'{et}\\' button -> Tapping ({cx}, {cy})", flush=True)
            tap(cx, cy)
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
        ad_t = (ad_e.get("text") or "") or ""
        ad_tt = ad_t.strip().lower()
        if any(kw in ad_tt for kw in ["play video", "final watch", "watch to unlock", "watch video", "install", "open app"]):
            ad_txt = ad_t or "install task"
            print(f"\\u2192 [INSTALL TASK] Detected: \\'{ad_txt}\\' -> Running install bypass BEFORE closing ad...", flush=True)
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
        print(f"\\U0001f4ca [SCREEN READ] Task counter after full 25s quiz cycle: \\'{new_counter}\\' (Before: \\'{prev_counter}\\' args)", flush=True)
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

'''
    text = text[:old_hab_start] + new_hab + text[old_hab_end:]
    print('Replaced handle_add_bonus_and_wait')

with open('free_ai_bot_reconstructed.py', 'w', encoding='utf-8') as f:
    f.write(text)

import py_compile
try:
    py_compile.compile('free_ai_bot_reconstructed.py', doraise=True)
    print('SYNTAX OK')
except Exception as e:
    print(f'SYNTAX ERROR: {e}')
