path = r"D:\KING PROJECT\Auto clicker\free_ai_bot.py"
with open(path, 'rb') as f:
    raw = f.read()
text = raw.decode('utf-8')
print(f'Original size: {len(text)} bytes')

changes = []

# ============================================================
# FIX 1: Stay-in-app guard at start of decide_and_execute_step()
# Insert after: all_text = " ".join([e["text"].lower() for e in elements])
# and before: # Check Done / Limit Over
# ============================================================

# The guard code as bytes to avoid quoting issues
guard_lines = [
    b'    # [STAY-IN-APP GUARD] If we left the quiz app (Play Store, Home, etc.),',
    b'    # force return immediately. Never operate outside the target app.',
    b'    _cur_pkg = get_current_app_package()',
    b'    _tgt_pkg = QUIZ_STATE.get("target_app_package") or "com.shake.master"',
    b'    if _cur_pkg and _cur_pkg != _tgt_pkg:',
    b'        print(b"\\n??? [STAY-IN-APP] Currently in \\'%s\\' (target: \\'%s\\'). Forcing return to quiz app..." % (_cur_pkg, _tgt_pkg), flush=True)',
    b'        # Press back repeatedly to exit overlays/Play Store',
    b'        for _bi in range(8):',
    b'            run_adb(["shell", "input", "keyevent", "4"])  # BACK',
    b'            time.sleep(0.4)',
    b'            _cp = get_current_app_package()',
    b'            if _cp == _tgt_pkg:',
    b'                print(b"??? [STAY-IN-APP] Returned to target app after %d back presses." % (_bi+1), flush=True)',
    b'                break',
    b'        # If still not in target, go home then launch target app',
    b'        _cp2 = get_current_app_package()',
    b'        if _cp2 != _tgt_pkg:',
    b'            print(b"??? [STAY-IN-APP] Still not in target (current: \\'%s\\'). Home + launch target..." % _cp2, flush=True)',
    b'            run_adb(["shell", "input", "keyevent", "3"])  # HOME',
    b'            time.sleep(1.0)',
    b'            run_adb(["shell", "monkey", "-p", _tgt_pkg, "-c", "android.intent.category.LAUNCHER", "1"])',
    b'            time.sleep(3.0)',
    b'            _cp3 = get_current_app_package()',
    b'            if _cp3 == _tgt_pkg:',
    b'                print(b"??? [STAY-IN-APP] Launched target app.", flush=True)',
    b'            else:',
    b'                print(b"??? [STAY-IN-APP] WARNING: Still not in target (\\'%s\\'). Retrying..." % _cp3, flush=True)',
    b'                for _ri in range(3):',
    b'                    run_adb(["shell", "input", "keyevent", "3"])',
    b'                    time.sleep(0.5)',
    b'                    run_adb(["shell", "monkey", "-p", _tgt_pkg, "-c", "android.intent.category.LAUNCHER", "1"])',
    b'                    time.sleep(3.0)',
    b'                    _cp4 = get_current_app_package()',
    b'                    if _cp4 == _tgt_pkg:',
    b'                        print(b"??? [STAY-IN-APP] Retry %d: Returned to target." % (_ri+1), flush=True)',
    b'                        break',
    b'        # Refresh elements after returning',
    b'        elements = get_ui_elements()',
    b'        all_text = " ".join([e["text"].lower() for e in elements])',
]

guard_block = b'\r\n'.join(guard_lines) + b'\r\n    \r\n'

# Find insertion point
anchor = b'    all_text = " ".join([e["text"].lower() for e in elements])\r\n    \r\n    # Check Done / Limit Over'
if anchor in raw:
    new_block = b'    all_text = " ".join([e["text"].lower() for e in elements])\r\n' + guard_block + b'    # Check Done / Limit Over'
    raw = raw.replace(anchor, new_block, 1)
    changes.append('FIX 1: stay-in-app guard added')
    print('FIX 1 applied')
else:
    # Try LF version
    anchor2 = b'    all_text = " ".join([e["text"].lower() for e in elements])\n    \n    # Check Done / Limit Over'
    if anchor2 in raw:
        guard_lf = b'\n'.join(guard_lines) + b'\n    \n'
        new_block2 = b'    all_text = " ".join([e["text"].lower() for e in elements])\n' + guard_lf + b'    # Check Done / Limit Over'
        raw = raw.replace(anchor2, new_block2, 1)
        changes.append('FIX 1: stay-in-app guard added (LF)')
        print('FIX 1 applied (LF)')
    else:
        print('FIX 1: anchor NOT found')
        # Find the line
        idx = text.find('all_text = " ".join')
        if idx > 0:
            ctx = text[idx:idx+100]
            print(f'  Context: {repr(ctx[:80])}')

# ============================================================
# FIX 2: In perform_fake_install_bypass, verify app after opening dummy
# After: monkey -p DUMMY_PACKAGE ... + time.sleep(5)
# Add: check current package, if not dummy app, back out
# ============================================================

verify_after_open = b'\r\n    # [VERIFY] After opening dummy app, check we are in dummy app (not Play Store)\r\n    _op_pkg = get_current_app_package()\r\n    if _op_pkg and _op_pkg != DUMMY_PACKAGE:\r\n        print(b"? [BYPASS VERIFY] Open returned to \\'%s\\' not dummy app. Dismissing..." % _op_pkg, flush=True)\r\n        for _vbi in range(5):\r\n            run_adb(["shell", "input", "keyevent", "4"])\r\n            time.sleep(0.4)\r\n            _vcp = get_current_app_package()\r\n            if _vcp == DUMMY_PACKAGE:\r\n                print(b"? [BYPASS VERIFY] Reached dummy after %d back presses." % (_vbi+1), flush=True)\r\n                break\r\n            if _vcp == target_app:\r\n                print(b"? [BYPASS VERIFY] Already back in target app.", flush=True)\r\n                break\r\n    \r\n'

# Find: monkey -p DUMMY_PACKAGE ... + time.sleep(5) + blank line + "# Step 4"
anchor3 = b'    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])\r\n    time.sleep(5)\r\n\r\n    # Step 4: Return to our app'
if anchor3 in raw:
    new3 = b'    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])\r\n    time.sleep(5)\r\n' + verify_after_open + b'    # Step 4: Return to our app'
    raw = raw.replace(anchor3, new3, 1)
    changes.append('FIX 2a: verify after opening dummy app')
    print('FIX 2a applied')
else:
    anchor3b = b'    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])\n    time.sleep(5)\n\n    # Step 4: Return to our app'
    if anchor3b in raw:
        vlf = b'\n    # [VERIFY] After opening dummy app, check we are in dummy app (not Play Store)\n    _op_pkg = get_current_app_package()\n    if _op_pkg and _op_pkg != DUMMY_PACKAGE:\n        print(b"? [BYPASS VERIFY] Open returned to \\'%s\\' not dummy app. Dismissing..." % _op_pkg, flush=True)\n        for _vbi in range(5):\n            run_adb(["shell", "input", "keyevent", "4"])\n            time.sleep(0.4)\n            _vcp = get_current_app_package()\n            if _vcp == DUMMY_PACKAGE:\n                print(b"? [BYPASS VERIFY] Reached dummy after %d back presses." % (_vbi+1), flush=True)\n                break\n            if _vcp == target_app:\n                print(b"? [BYPASS VERIFY] Already back in target app.", flush=True)\n                break\n    \n'
        new3b = b'    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])\n    time.sleep(5)\n' + vlf + b'    # Step 4: Return to our app'
        raw = raw.replace(anchor3b, new3b, 1)
        changes.append('FIX 2a: verify after opening dummy (LF)')
        print('FIX 2a applied (LF)')
    else:
        print('FIX 2a: anchor NOT found')

# ============================================================
# FIX 3: In perform_fake_install_bypass, verify after returning to target app
# After: monkey -p target_app + time.sleep(2.5) + blank + "# Step 5"
# ============================================================

verify_after_return = b'\r\n    # [VERIFY] Confirm we are back in target app\r\n    _back_pkg = get_current_app_package()\r\n    if _back_pkg != target_app:\r\n        print(b"? [BYPASS VERIFY] Return failed (got \\'%s\\' not \\'%s\\'). Force-launching..." % (_back_pkg, target_app), flush=True)\r\n        for _fi in range(5):\r\n            run_adb(["shell", "input", "keyevent", "3"])\r\n            time.sleep(0.5)\r\n            run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])\r\n            time.sleep(3.0)\r\n            _bp = get_current_app_package()\r\n            if _bp == target_app:\r\n                print(b"? [BYPASS VERIFY] Force-launch OK on attempt %d." % (_fi+1), flush=True)\r\n                break\r\n    \r\n'

anchor4 = b'    time.sleep(2.5)\r\n\r\n    # Step 5: Check screen according to actual UI elements (No blind forced click)'
# This needs to be within perform_fake_install_bypass context
# Find the one that's right after monkey -p target_app
idx = text.find('monkey", "-p", target_app')
if idx > 0:
    # Find the time.sleep(2.5) after this
    sleep_idx = text.find('time.sleep(2.5)', idx)
    if sleep_idx > 0:
        # Check if this is followed by Step 5 comment
        after_sleep = text[sleep_idx:sleep_idx+100]
        if '# Step 5' in after_sleep or 'Step 5' in after_sleep:
            # Build the replacement
            old4 = text[sleep_idx-5:sleep_idx+80]  # approximate
            # More precise: find from monkey line to Step 5 comment
            start = text.rfind(b'\r\n', 0, sleep_idx) if isinstance(text, str) else text.rfind(b'\n', 0, sleep_idx)
            # Actually work with bytes
            pass

# Simpler: find the specific pattern in the function
# In perform_fake_install_bypass, the Step 4 section has:
#   run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])
#   time.sleep(2.5)
#   (blank)
#   # Step 5: Check screen...

# Find all occurrences of this pattern
pos = 0
found = False
while True:
    pos = text.find('run_adb(["shell", "monkey", "-p", target_app', pos)
    if pos == -1:
        break
    # Check if followed by time.sleep(2.5) then Step 5
    snippet = text[pos:pos+300]
    if 'time.sleep(2.5)' in snippet and '# Step 5' in snippet:
        # This is the right one (inside perform_fake_install_bypass)
        # Find exact boundaries
        line_start = text.rfind('\n', 0, pos) + 1
        step5_idx = text.find('# Step 5: Check screen', pos)
        line_end = text.find('\n', step5_idx) + 1
        
        old_section = text[line_start:line_end]
        
        # Build replacement
        new_section = (
            '    run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])\r\n'
            '    time.sleep(2.5)\r\n'
            '\r\n'
            '    # [VERIFY] Confirm we are back in target app\r\n'
            '    _back_pkg = get_current_app_package()\r\n'
            '    if _back_pkg != target_app:\r\n'
            '        print(f"? [BYPASS VERIFY] Return failed (got \\'{_back_pkg}\\' not \\'{target_app}\\'). Force-launching...", flush=True)\r\n'
            '        for _fi in range(5):\r\n'
            '            run_adb(["shell", "input", "keyevent", "3"])\r\n'
            '            time.sleep(0.5)\r\n'
            '            run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])\r\n'
            '            time.sleep(3.0)\r\n'
            '            _bp = get_current_app_package()\r\n'
            '            if _bp == target_app:\r\n'
            '                print(f"? [BYPASS VERIFY] Force-launch OK on attempt {_fi+1}.", flush=True)\r\n'
            '                break\r\n'
            '\r\n'
            '    # Step 5: Check screen according to actual UI elements (No blind forced click)'
        )
        
        text = text[:line_start] + new_section + text[line_end:]
        changes.append('FIX 3: verify after returning to target app')
        print(f'FIX 3 applied at position {line_start}')
        found = True
        break
    pos += 1

if not found:
    # Try LF version
    pos = 0
    while True:
        pos = text.find('run_adb(["shell", "monkey", "-p", target_app', pos)
        if pos == -1:
            break
        snippet = text[pos:pos+300]
        if 'time.sleep(2.5)' in snippet and '# Step 5' in snippet:
            line_start = text.rfind('\n', 0, pos) + 1
            step5_idx = text.find('# Step 5: Check screen', pos)
            line_end = text.find('\n', step5_idx) + 1
            old_section = text[line_start:line_end]
            new_section = (
                '    run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])\n'
                '    time.sleep(2.5)\n'
                '\n'
                '    # [VERIFY] Confirm we are back in target app\n'
                '    _back_pkg = get_current_app_package()\n'
                '    if _back_pkg != target_app:\n'
                '        print(f"? [BYPASS VERIFY] Return failed (got \\'{_back_pkg}\\' not \\'{target_app}\\'). Force-launching...", flush=True)\n'
                '        for _fi in range(5):\n'
                '            run_adb(["shell", "input", "keyevent", "3"])\n'
                '            time.sleep(0.5)\n'
                '            run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])\n'
                '            time.sleep(3.0)\n'
                '            _bp = get_current_app_package()\n'
                '            if _bp == target_app:\n'
                '                print(f"? [BYPASS VERIFY] Force-launch OK on attempt {_fi+1}.", flush=True)\n'
                '                break\n'
                '\n'
                '    # Step 5: Check screen according to actual UI elements (No blind forced click)'
            )
            text = text[:line_start] + new_section + text[line_end:]
            changes.append('FIX 3: verify after return (LF)')
            print(f'FIX 3 applied (LF) at {line_start}')
            found = True
            break
        pos += 1

if not found:
    print('FIX 3: pattern NOT found')

# ============================================================
# FIX 4: Reset quiz state after install-bypass so next cycle re-answers
# Find: perform_fake_install_bypass() + return False, "INSTALL_BYPASS_EXECUTED"
# ============================================================

for pattern, replacement in [
    # In handle_add_bonus_and_wait (quiz repeat 3x path)
    (
        '                perform_fake_install_bypass()\r\n'
        '                return False, "INSTALL_BYPASS_EXECUTED"',
        '                perform_fake_install_bypass()\r\n'
        '                QUIZ_STATE["last_quiz_id"] = None\r\n'
        '                QUIZ_STATE["repeat_count"] = 0\r\n'
        '                return False, "INSTALL_BYPASS_EXECUTED"'
    ),
    # In decide_and_execute_step quiz repeat path
    (
        '            perform_fake_install_bypass()\r\n'
        '            return False, "INSTALL_BYPASS_EXECUTED"',
        '            perform_fake_install_bypass()\r\n'
        '            QUIZ_STATE["last_quiz_id"] = None\r\n'
        '            QUIZ_STATE["repeat_count"] = 0\r\n'
        '            return False, "INSTALL_BYPASS_EXECUTED"'
    ),
    # Final Watch path
    (
        '                perform_fake_install_bypass()\r\n'
        '                return False, "FINAL_WATCH_BYPASS"',
        '                perform_fake_install_bypass()\r\n'
        '                QUIZ_STATE["last_quiz_id"] = None\r\n'
        '                QUIZ_STATE["repeat_count"] = 0\r\n'
        '                return False, "FINAL_WATCH_BYPASS"'
    ),
]:
    if pattern in text:
        text = text.replace(pattern, replacement, 1)
        changes.append(f'QUIZ RESET: replaced pattern')
        print(f'Quiz reset applied for pattern')
    else:
        # Try LF
        pl = pattern.replace('\r\n', '\n')
        rl = replacement.replace('\r\n', '\n')
        if pl in text:
            text = text.replace(pl, rl, 1)
            changes.append(f'QUIZ RESET (LF)')
            print(f'Quiz reset applied (LF)')
        else:
            print(f'Pattern NOT found: {pattern[:60]}...')

# ============================================================
# FIX 5: During ad/close handling, be very careful not to click
# wrong areas that redirect to Play Store or Chrome.
# In handle_add_bonus_and_wait(), after tapping Add Bonus and
# the ad opens, only dismiss the ad at the known safe coordinates
# or via UI element text match. Never do blind taps.
# ============================================================

# The dismiss_ad_if_present() function should only tap elements
# with specific text or at very specific safe coordinates.
# Let me check and fix it if needed.

# Find dismiss_ad_if_present
dismiss_idx = text.find('def dismiss_ad_if_present(')
if dismiss_idx > 0:
    dismiss_end = text.find('\ndef ', dismiss_idx + 1)
    if dismiss_end == -1:
        dismiss_end = dismiss_idx + 500
    dismiss_func = text[dismiss_idx:dismiss_end]
    
    # Check what it does - if it does blind taps, make it safer
    if '1013' in dismiss_func or '176' in dismiss_func:
        # It has hardcoded coordinates - make it check text first
        changes.append('CHECK: dismiss_ad_if_present has hardcoded coords')
        print('dismiss_ad_if_present uses hardcoded coords (1013,176) - considering safer approach')
    else:
        changes.append('CHECK: dismiss_ad_if_present uses UI elements')
        print('dismiss_ad_if_present uses UI element matching')
    
    # Print the function for review
    for i, line in enumerate(dismiss_func.split('\n')[:30]):
        out = ''.join(c if ord(c) < 128 else '?' for c in line)
        print(f'  {i:3d}: {out}')

# ============================================================
# FIX 6: In the AI Vision / Ollama event handler, when the AI
# returns CLOSE_AD or CLICK, verify the target is within the
# quiz app screen area and is a known safe button.
# Don't blindly tap AI-suggested coordinates that might be
# in a different app or on ad redirects.
# ============================================================

# Find the ollama action handling section
ollama_action_idx = text.find('if ollama_decision and ollama_decision.get("action") == "CLICK":')
if ollama_action_idx > 0:
    # Add safety check: verify click is within safe area
    # Find the tap call after this
    tap_idx = text.find('tap(click_x, click_y)', ollama_action_idx)
    if tap_idx > 0:
        # Add a safety check before the tap
        safety_check = (
            '            # [SAFE CLICK] Verify click is within app screen bounds\r\n'
            '            # Only tap if coordinates are reasonable (not in status bar, not off-screen)\r\n'
            '            if click_x and click_y:\r\n'
            '                if 50 <= click_x <= 1030 and 200 <= click_y <= 2200:\r\n'
            '                    tap(click_x, click_y)\r\n'
            '                    time.sleep(2)\r\n'
            '                    return False, "OLLAMA_EVENT_CLICK"\r\n'
            '                else:\r\n'
            '                    print(f"? [SAFE CLICK] AI suggested out-of-bounds click ({click_x}, {click_y}) - skipping.", flush=True)\r\n'
        )
        # Replace the existing if click_x block
        old_block = (
            '            if click_x and click_y:\r\n'
            '                print(f"? [OLLAMA ACTION] Resolved event popup -> Tapping ({click_x}, {click_y}) | Reason: {reason}", flush=True)\r\n'
            '                tap(click_x, click_y)\r\n'
            '                time.sleep(2)\r\n'
            '                return False, "OLLAMA_EVENT_CLICK"\r\n'
        )
        if old_block in text:
            text = text.replace(old_block, safety_check, 1)
            changes.append('FIX 6: safe click bounds check in Ollama handler')
            print('FIX 6 applied: safe click bounds')
        else:
            print('FIX 6: old block not found')

# ============================================================
# Write the fixed file
# ============================================================
with open(path, 'wb') as f:
    f.write(text.encode('utf-8'))

print(f'\n=== TOTAL CHANGES: {len(changes)} ===')
for c in changes:
    print(f'  - {c}')

# Syntax check with bytes
import py_compile
try:
    py_compile.compile(path, doraise=True)
    print('\n=== SYNTAX OK ===')
except Exception as e:
    print(f'\n=== SYNTAX ERROR: {e} ===')
    # Show the problematic area
    import traceback
    tb = traceback.format_exc()
    print(tb[:1000])
