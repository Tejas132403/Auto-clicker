path = r"D:\KING PROJECT\Auto clicker\free_ai_bot.py"
with open(path, 'rb') as f:
    raw = f.read()
text = raw.decode('utf-8')
print(f'Original size: {len(text)} bytes')

# Read guard code from file
with open('guard_code.txt', 'r', encoding='utf-8') as f:
    guard_text = f.read()

# Detect line ending style in the guard code
guard_lines = guard_text.split('\n')
# Re-join with the file's line ending style
# Check what line ending free_ai_bot.py uses around the insertion point
idx = text.find('all_text = " ".join([e["text"].lower() for e in elements])')
if idx > 0:
    next_100 = text[idx:idx+100]
    if b'\r\n' in next_100.encode():
        le = '\r\n'
    else:
        le = '\n'
else:
    le = '\n'

guard_block = le.join(guard_lines) + le + le

# Find insertion point and insert guard
anchor = '    all_text = " ".join([e["text"].lower() for e in elements])' + le + le + '    # Check Done / Limit Over'
if anchor in text:
    replacement = '    all_text = " ".join([e["text"].lower() for e in elements])' + le + guard_block + '    # Check Done / Limit Over'
    text = text.replace(anchor, replacement, 1)
    print('FIX 1: stay-in-app guard inserted')
else:
    # Try without double blank line
    anchor2 = '    all_text = " ".join([e["text"].lower() for e in elements])' + le + '    # Check Done / Limit Over'
    if anchor2 in text:
        replacement2 = '    all_text = " ".join([e["text"].lower() for e in elements])' + le + guard_block + '    # Check Done / Limit Over'
        text = text.replace(anchor2, replacement2, 1)
        print('FIX 1: guard inserted (no blank line)')
    else:
        print('FIX 1: anchor not found, trying to locate...')
        idx = text.find('all_text = " ".join')
        if idx >= 0:
            ctx = text[idx:idx+80]
            print(f'  Found at {idx}: {repr(ctx[:60])}')

# FIX 2a: Add verification after opening dummy app in perform_fake_install_bypass
verify_open = le + le + (
    '    # [BYPASS VERIFY] After opening dummy app, check we are in dummy app (not Play Store)\n'
    '    _op_pkg = get_current_app_package()\n'
    '    if _op_pkg and _op_pkg != DUMMY_PACKAGE:\n'
    '        print(f"? [BYPASS VERIFY] Open returned to \\'{_op_pkg}\\' not dummy. Dismissing...", flush=True)\n'
    '        for _vbi in range(5):\n'
    '            run_adb(["shell", "input", "keyevent", "4"])\n'
    '            time.sleep(0.4)\n'
    '            _vcp = get_current_app_package()\n'
    '            if _vcp == DUMMY_PACKAGE:\n'
    '                print(f"? [BYPASS VERIFY] Reached dummy after {_vbi+1} back presses.", flush=True)\n'
    '                break\n'
    '            if _vcp == target_app:\n'
    '                print("? [BYPASS VERIFY] Already back in target app.", flush=True)\n'
    '                break\n'
)

# Find: monkey -p DUMMY_PACKAGE + time.sleep(5) + blank + "# Step 4"
pattern2a = (
    '    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])' + le +
    '    time.sleep(5)' + le + le +
    '    # Step 4: Return to our app'
)
if pattern2a in text:
    replacement2a = (
        '    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])' + le +
        '    time.sleep(5)' + verify_open +
        '    # Step 4: Return to our app'
    )
    text = text.replace(pattern2a, replacement2a, 1)
    print('FIX 2a: verify after opening dummy app')
else:
    print('FIX 2a: pattern not found')

# FIX 3: Add verification after returning to target app
verify_return = le + le + (
    '    # [VERIFY] Confirm we are back in target app\n'
    '    _back_pkg = get_current_app_package()\n'
    '    if _back_pkg != target_app:\n'
    '        print(f"? [BYPASS VERIFY] Return failed (got \\'{_back_pkg}\\' not \\'{target_app}\\$'). Force-launching...", flush=True)\n'
    '        for _fi in range(5):\n'
    '            run_adb(["shell", "input", "keyevent", "3"])\n'
    '            time.sleep(0.5)\n'
    '            run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])\n'
    '            time.sleep(3.0)\n'
    '            _bp = get_current_app_package()\n'
    '            if _bp == target_app:\n'
    '                print(f"? [BYPASS VERIFY] Force-launch OK on attempt {_fi+1}.", flush=True)\n'
    '                break\n'
)

pattern3 = (
    '    time.sleep(2.5)' + le + le +
    '    # Step 5: Check screen according to actual UI elements (No blind forced click)'
)
# This pattern might appear multiple times - find the one inside perform_fake_install_bypass
pos = 0
found3 = False
while True:
    pos = text.find('run_adb(["shell", "monkey", "-p", target_app', pos)
    if pos == -1:
        break
    snippet = text[pos:pos+400]
    if 'time.sleep(2.5)' in snippet and '# Step 5: Check screen' in snippet:
        # Found the right one
        # Find the exact boundaries
        start = text.rfind(le, 0, pos) + len(le)
        step5_pos = text.find('# Step 5: Check screen', pos)
        end = text.find(le, step5_pos) + len(le)
        old_section = text[start:end]
        
        new_section = (
            '    run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])' + le +
            '    time.sleep(2.5)' + verify_return +
            '    # Step 5: Check screen according to actual UI elements (No blind forced click)'
        )
        text = text[:start] + new_section + text[end:]
        print(f'FIX 3: verify after return to target (at pos {start})')
        found3 = True
        break
    pos += 1

if not found3:
    print('FIX 3: pattern not found')

# FIX 4: Reset quiz state after install-bypass (multiple locations)
for old_p, new_p in [
    (
        '                perform_fake_install_bypass()' + le + '                return False, "INSTALL_BYPASS_EXECUTED"',
        '                perform_fake_install_bypass()' + le + '                QUIZ_STATE["last_quiz_id"] = None' + le + '                QUIZ_STATE["repeat_count"] = 0' + le + '                return False, "INSTALL_BYPASS_EXECUTED"'
    ),
    (
        '            perform_fake_install_bypass()' + le + '            return False, "INSTALL_BYPASS_EXECUTED"',
        '            perform_fake_install_bypass()' + le + '            QUIZ_STATE["last_quiz_id"] = None' + le + '            QUIZ_STATE["repeat_count"] = 0' + le + '            return False, "INSTALL_BYPASS_EXECUTED"'
    ),
    (
        '                perform_fake_install_bypass()' + le + '                return False, "FINAL_WATCH_BYPASS"',
        '                perform_fake_install_bypass()' + le + '                QUIZ_STATE["last_quiz_id"] = None' + le + '                QUIZ_STATE["repeat_count"] = 0' + le + '                return False, "FINAL_WATCH_BYPASS"'
    ),
]:
    if old_p in text:
        text = text.replace(old_p, new_p, 1)
        print(f'FIX 4: quiz reset applied for one bypass return')
        break
else:
    print('FIX 4: no bypass return pattern found')

# FIX 5: Safe click bounds in Ollama event handler
old_ollama_click = (
    '            if click_x and click_y:' + le +
    '                print(f"? [OLLAMA ACTION] Resolved event popup -> Tapping ({click_x}, {click_y}) | Reason: {reason}", flush=True)' + le +
    '                tap(click_x, click_y)' + le +
    '                time.sleep(2)' + le +
    '                return False, "OLLAMA_EVENT_CLICK"' + le
)
if old_ollama_click in text:
    new_ollama_click = (
        '            if click_x and click_y:' + le +
        '                # [SAFE CLICK] Only tap within safe screen bounds (not status bar, not off-screen)' + le +
        '                if 50 <= click_x <= 1030 and 200 <= click_y <= 2200:' + le +
        '                    print(f"? [OLLAMA ACTION] Resolved -> Tapping ({click_x}, {click_y}) | Reason: {reason}", flush=True)' + le +
        '                    tap(click_x, click_y)' + le +
        '                    time.sleep(2)' + le +
        '                    return False, "OLLAMA_EVENT_CLICK"' + le +
        '                else:' + le +
        '                    print(f"? [SAFE CLICK] AI suggested out-of-bounds ({click_x}, {click_y}) - skipping.", flush=True)' + le +
        '                    return False, "OLLAMA_SKIPPED_UNSAFE"' + le
    )
    text = text.replace(old_ollama_click, new_ollama_click, 1)
    print('FIX 5: safe click bounds in Ollama handler')
else:
    print('FIX 5: Ollama click pattern not found')

# Write fixed file
with open(path, 'wb') as f:
    f.write(text.encode('utf-8'))

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print('\n=== SYNTAX OK ===')
except Exception as e:
    print(f'\n=== SYNTAX ERROR: {e} ===')

print(f'Final size: {len(text)} bytes')
