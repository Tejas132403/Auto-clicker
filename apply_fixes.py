path = r"D:\KING PROJECT\Auto clicker\free_ai_bot.py"
with open(path, 'rb') as f:
    raw = f.read()
text = raw.decode('utf-8')

# ============================================================
# FIX 1: Add "stay in app" guard at the start of
# decide_and_execute_step()
# ============================================================
# Find the line after getting elements:
#     elements = get_ui_elements()
#     all_text = " ".join([e["text"].lower() for e in elements])
# Insert stay-in-app check after this

guard_code = '''
    # [STAY-IN-APP GUARD] Ensure we never operate outside the target app.
    # If the phone is in Play Store, Home, or any other app, force-return
    # to the quiz app before doing anything else. This prevents the bot from
    # getting stuck outside the app (e.g., in Play Store after an install).
    _current_pkg = get_current_app_package()
    _target_pkg = QUIZ_STATE.get("target_app_package") or "com.shake.master"
    if _current_pkg and _current_pkg != _target_pkg:
        # We are outside the target app - force return
        print(f"\\n??? [STAY-IN-APP] Currently in '{_current_pkg}' (target: '{_target_pkg}'). Forcing return to quiz app...", flush=True)
        # Press back repeatedly to exit any overlays/Play Store
        for _back_i in range(8):
            run_adb(["shell", "input", "keyevent", "4"])  # BACK
            time.sleep(0.4)
            _cp = get_current_app_package()
            if _cp == _target_pkg:
                print(f"??? [STAY-IN-APP] Returned to target app after {_back_i+1} back presses.", flush=True)
                break
            if _cp in (None, _target_pkg):
                break
        # If still not in target app, go home then launch target
        _cp2 = get_current_app_package()
        if _cp2 != _target_pkg:
            print(f"??? [STAY-IN-APP] Still not in target app (current: '{_cp2}'). Going Home then launching target app...", flush=True)
            run_adb(["shell", "input", "keyevent", "3"])  # HOME
            time.sleep(1.0)
            run_adb(["shell", "monkey", "-p", _target_pkg, "-c", "android.intent.category.LAUNCHER", "1"])
            time.sleep(3.0)
            _cp3 = get_current_app_package()
            if _cp3 == _target_pkg:
                print(f"??? [STAY-IN-APP] Launched target app successfully.", flush=True)
            else:
                print(f"??? [STAY-IN-APP] WARNING: Could not return to target app. Current: '{_cp3}'. Retrying...", flush=True)
                for _retry in range(3):
                    run_adb(["shell", "input", "keyevent", "3"])
                    time.sleep(0.5)
                    run_adb(["shell", "monkey", "-p", _target_pkg, "-c", "android.intent.category.LAUNCHER", "1"])
                    time.sleep(3.0)
                    _cp4 = get_current_app_package()
                    if _cp4 == _target_pkg:
                        print(f"??? [STAY-IN-APP] Retry {_retry+1}: Returned to target app.", flush=True)
                        break
        # Update elements and text after returning
        elements = get_ui_elements()
        all_text = " ".join([e["text"].lower() for e in elements])
'''

# Find insertion point: after "all_text = ..." line in decide_and_execute_step
old_guard_anchor = '    all_text = " ".join([e["text"].lower() for e in elements])\r\n    \r\n    # Check Done / Limit Over'
new_guard = '    all_text = " ".join([e["text"].lower() for e in elements])\r\n' + guard_code + '\r\n    # Check Done / Limit Over'

print(f'Guard anchor found: {old_guard_anchor in text}')
if old_guard_anchor in text:
    text = text.replace(old_guard_anchor, new_guard, 1)
    print('FIX 1 applied: stay-in-app guard added')
else:
    # Try without \r\n
    old2 = '    all_text = " ".join([e["text"].lower() for e in elements])\n    \n    # Check Done / Limit Over'
    print(f'Guard anchor v2 found: {old2 in text}')
    if old2 in text:
        new2 = '    all_text = " ".join([e["text"].lower() for e in elements])\n' + guard_code.replace('\r\n', '\n') + '\n    # Check Done / Limit Over'
        text = text.replace(old2, new2, 1)
        print('FIX 1 applied (v2)')

# ============================================================
# FIX 2: Fix perform_fake_install_bypass to verify app stays
# ============================================================
# Step 3: After opening dummy app, verify we're in dummy app (not Play Store)
# Find: run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, ...]) then time.sleep(5)
# Add verification after the sleep

old_step3 = (
    '    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])\r\n'
    '    time.sleep(5)\r\n'
    '\r\n'
    '    # Step 4: Return to our app'
)

new_step3 = (
    '    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])\r\n'
    '    time.sleep(5)\r\n'
    '\r\n'
    '    # [VERIFY] Check we are actually in the dummy app (not Play Store or other)\r\n'
    '    _opened_pkg = get_current_app_package()\r\n'
    '    if _opened_pkg and _opened_pkg != DUMMY_PACKAGE:\r\n'
    '        print(f"? [BYPASS VERIFY] Opening returned to \\'{_opened_pkg}\\' instead of dummy app. Dismissing and continuing...", flush=True)\r\n'
    '        # If Play Store or other app opened, dismiss with back\r\n'
    '        for _bi in range(5):\r\n'
    '            run_adb(["shell", "input", "keyevent", "4"])\r\n'
    '            time.sleep(0.4)\r\n'
    '            _cp = get_current_app_package()\r\n'
    '            if _cp == DUMMY_PACKAGE:\r\n'
    '                print(f"? [BYPASS VERIFY] Reached dummy app after {_bi+1} back presses.", flush=True)\r\n'
    '                break\r\n'
    '            if _cp == _target_app:\r\n'
    '                print(f"? [BYPASS VERIFY] Already back in target app.", flush=True)\r\n'
    '                break\r\n'
    '\r\n'
    '    # Step 4: Return to our app'
)

print(f'Step3 anchor found: {old_step3 in text}')
if old_step3 in text:
    text = text.replace(old_step3, new_step3, 1)
    print('FIX 2a applied: dummy app verification after open')
else:
    print('Step3 anchor NOT found - trying LF version')
    old3b = (
        '    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])\n'
        '    time.sleep(5)\n'
        '\n'
        '    # Step 4: Return to our app'
    )
    print(f'  v2 found: {old3b in text}')
    if old3b in text:
        new3b = (
            '    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])\n'
            '    time.sleep(5)\n'
            '\n'
            '    # [VERIFY] Check we are actually in the dummy app (not Play Store or other)\n'
            '    _opened_pkg = get_current_app_package()\n'
            '    if _opened_pkg and _opened_pkg != DUMMY_PACKAGE:\n'
            '        print(f"? [BYPASS VERIFY] Opening returned to \\'{_opened_pkg}\\' instead of dummy app. Dismissing and continuing...", flush=True)\n'
            '        for _bi in range(5):\n'
            '            run_adb(["shell", "input", "keyevent", "4"])\n'
            '            time.sleep(0.4)\n'
            '            _cp = get_current_app_package()\n'
            '            if _cp == DUMMY_PACKAGE:\n'
            '                print(f"? [BYPASS VERIFY] Reached dummy app after {_bi+1} back presses.", flush=True)\n'
            '                break\n'
            '            if _cp == _target_app:\n'
            '                print(f"? [BYPASS VERIFY] Already back in target app.", flush=True)\n'
            '                break\n'
            '\n'
            '    # Step 4: Return to our app'
        )
        text = text.replace(old3b, new3b, 1)
        print('FIX 2a applied (v2)')

# Step 4: After returning to target app, verify we're there
old_step4 = (
    '    run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])\r\n'
    '    time.sleep(2.5)\r\n'
    '\r\n'
    '    # Step 5: Check screen according to actual UI elements (No blind forced click)'
)

new_step4 = (
    '    run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])\r\n'
    '    time.sleep(2.5)\r\n'
    '\r\n'
    '    # [VERIFY] Confirm we are back in the target app\r\n'
    '    _back_pkg = get_current_app_package()\r\n'
    '    if _back_pkg != target_app:\r\n'
    '        print(f"? [BYPASS VERIFY] Return to target app failed (got \\'{_back_pkg}\\' instead of \\'{target_app}\\'). Forcing launch...", flush=True)\r\n'
    '        for _force in range(5):\r\n'
    '            run_adb(["shell", "input", "keyevent", "3"])\r\n'
    '            time.sleep(0.5)\r\n'
    '            run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])\r\n'
    '            time.sleep(3.0)\r\n'
    '            _bp = get_current_app_package()\r\n'
    '            if _bp == target_app:\r\n'
    '                print(f"? [BYPASS VERIFY] Force-launch succeeded on attempt {_force+1}.", flush=True)\r\n'
    '                break\r\n'
    '\r\n'
    '    # Step 5: Check screen according to actual UI elements (No blind forced click)'
)

print(f'Step4 anchor found: {old_step4 in text}')
if old_step4 in text:
    text = text.replace(old_step4, new_step4, 1)
    print('FIX 2b applied: target app verification after return')
else:
    old4b = (
        '    run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])\n'
        '    time.sleep(2.5)\n'
        '\n'
        '    # Step 5: Check screen according to actual UI elements (No blind forced click)'
    )
    print(f'  Step4 v2 found: {old4b in text}')
    if old4b in text:
        new4b = (
            '    run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])\n'
            '    time.sleep(2.5)\n'
            '\n'
            '    # [VERIFY] Confirm we are back in the target app\n'
            '    _back_pkg = get_current_app_package()\n'
            '    if _back_pkg != target_app:\n'
            '        print(f"? [BYPASS VERIFY] Return to target app failed (got \\'{_back_pkg}\\' instead of \\'{target_app}\\'). Forcing launch...", flush=True)\n'
            '        for _force in range(5):\n'
            '            run_adb(["shell", "input", "keyevent", "3"])\n'
            '            time.sleep(0.5)\n'
            '            run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])\n'
            '            time.sleep(3.0)\n'
            '            _bp = get_current_app_package()\n'
            '            if _bp == target_app:\n'
            '                print(f"? [BYPASS VERIFY] Force-launch succeeded on attempt {_force+1}.", flush=True)\n'
            '                break\n'
            '\n'
            '    # Step 5: Check screen according to actual UI elements (No blind forced click)'
        )
        text = text.replace(old4b, new4b, 1)
        print('FIX 2b applied (v2)')

# ============================================================
# FIX 3: After handle_add_bonus_and_wait returns with
# INSTALL_BYPASS_EXECUTED, re-answer the quiz in the next cycle
# ============================================================
# The issue: after install-bypass, counter is same (9/25), quiz already answered
# But the bot doesn't re-answer. We need to reset the quiz state so it re-answers.
# 
# In handle_add_bonus_and_wait(), after "INSTALL_BYPASS_EXECUTED" return:
# Set last_quiz_id = None so the next cycle re-detects the quiz.

old_handle_return = (
    '                perform_fake_install_bypass()\r\n'
    '                return False, "INSTALL_BYPASS_EXECUTED"'
)

new_handle_return = (
    '                perform_fake_install_bypass()\r\n'
    '                # [RE-ANSWER] Reset quiz state so next cycle re-answers the quiz\r\n'
    '                QUIZ_STATE["last_quiz_id"] = None\r\n'
    '                QUIZ_STATE["repeat_count"] = 0\r\n'
    '                return False, "INSTALL_BYPASS_EXECUTED"'
)

print(f'Handle return anchor found: {old_handle_return in text}')
if old_handle_return in text:
    text = text.replace(old_handle_return, new_handle_return, 1)
    print('FIX 3 applied: re-answer quiz after install-bypass')
else:
    print('Handle return anchor NOT found')

# Also fix other perform_fake_install_bypass() calls that return INSTALL_BYPASS_EXECUTED
# The quiz repeat detection also calls it
old_quiz_return = (
    '            perform_fake_install_bypass()\r\n'
    '            return False, "INSTALL_BYPASS_EXECUTED"'
)

new_quiz_return = (
    '            perform_fake_install_bypass()\r\n'
    '            QUIZ_STATE["last_quiz_id"] = None\r\n'
    '            QUIZ_STATE["repeat_count"] = 0\r\n'
    '            return False, "INSTALL_BYPASS_EXECUTED"'
)

print(f'Quiz return anchor found: {old_quiz_return in text}')
if old_quiz_return in text:
    text = text.replace(old_quiz_return, new_quiz_return, 1)
    print('FIX 3b applied: re-answer quiz after quiz-repeat bypass')
else:
    print('Quiz return anchor NOT found - checking LF version')
    old_qr2 = (
        '            perform_fake_install_bypass()\n'
        '            return False, "INSTALL_BYPASS_EXECUTED"'
    )
    print(f'  v2 found: {old_qr2 in text}')
    if old_qr2 in text:
        new_qr2 = (
            '            perform_fake_install_bypass()\n'
            '            QUIZ_STATE["last_quiz_id"] = None\n'
            '            QUIZ_STATE["repeat_count"] = 0\n'
            '            return False, "INSTALL_BYPASS_EXECUTED"'
        )
        text = text.replace(old_qr2, new_qr2, 1)
        print('FIX 3b applied (v2)')

# ============================================================
# FIX 4: Also fix the Final Watch bypass to reset quiz state
# ============================================================
old_fw_return = (
    '                perform_fake_install_bypass()\r\n'
    '                return False, "FINAL_WATCH_BYPASS"'
)

new_fw_return = (
    '                perform_fake_install_bypass()\r\n'
    '                QUIZ_STATE["last_quiz_id"] = None\r\n'
    '                QUIZ_STATE["repeat_count"] = 0\r\n'
    '                return False, "FINAL_WATCH_BYPASS"'
)

print(f'Final Watch return anchor found: {old_fw_return in text}')
if old_fw_return in text:
    text = text.replace(old_fw_return, new_fw_return, 1)
    print('FIX 4 applied: reset quiz after Final Watch bypass')
else:
    old_fw2 = (
        '                perform_fake_install_bypass()\n'
        '                return False, "FINAL_WATCH_BYPASS"'
    )
    print(f'  FW v2 found: {old_fw2 in text}')
    if old_fw2 in text:
        new_fw2 = (
            '                perform_fake_install_bypass()\n'
            '                QUIZ_STATE["last_quiz_id"] = None\n'
            '                QUIZ_STATE["repeat_count"] = 0\n'
            '                return False, "FINAL_WATCH_BYPASS"'
        )
        text = text.replace(old_fw2, new_fw2, 1)
        print('FIX 4 applied (v2)')

# Verify
with open(path, 'wb') as f:
    f.write(text.encode('utf-8'))

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print('\n=== SYNTAX OK ===')
except Exception as e:
    print(f'\n=== SYNTAX ERROR: {e} ===')

# Count fixes
for name, needle in [
    ('STAY-IN-APP', 'STAY-IN-APP'),
    ('BYPASS VERIFY', 'BYPASS VERIFY'),
    ('RE-ANSWER', 'RE-ANSWER'),
]:
    print(f'{name}: {text.count(needle)}')
