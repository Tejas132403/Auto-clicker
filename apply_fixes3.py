path = r"D:\KING PROJECT\Auto clicker\free_ai_bot.py"
with open(path, 'rb') as f:
    raw = f.read()
text = raw.decode('utf-8')
print(f'Original size: {len(text)} bytes')

le = '\r\n'  # free_ai_bot.py uses CRLF

# Read code blocks from files (avoids all quoting issues)
with open('verify_open.txt', 'r') as f:
    verify_open = f.read()
with open('verify_return.txt', 'r') as f:
    verify_return = f.read()

# FIX 1: Stay-in-app guard
# Read guard from guard_code.txt
with open('guard_code.txt', 'r') as f:
    guard_text = f.read()
guard_block = le + le + guard_text + le

anchor1 = '    all_text = " ".join([e["text"].lower() for e in elements])' + le + le + '    # Check Done / Limit Over'
if anchor1 in text:
    replacement1 = '    all_text = " ".join([e["text"].lower() for e in elements])' + guard_block + '    # Check Done / Limit Over'
    text = text.replace(anchor1, replacement1, 1)
    print('FIX 1: stay-in-app guard inserted')
else:
    anchor1b = '    all_text = " ".join([e["text"].lower() for e in elements])' + le + '    # Check Done / Limit Over'
    if anchor1b in text:
        replacement1b = '    all_text = " ".join([e["text"].lower() for e in elements])' + guard_block + '    # Check Done / Limit Over'
        text = text.replace(anchor1b, replacement1b, 1)
        print('FIX 1: guard inserted (alt anchor)')
    else:
        print('FIX 1: NOT FOUND')

# FIX 2a: Verify after opening dummy app
p2a = ('    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])' + le +
       '    time.sleep(5)' + le + le +
       '    # Step 4: Return to our app')
r2a = ('    run_adb(["shell", "monkey", "-p", DUMMY_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])' + le +
       '    time.sleep(5)' + verify_open +
       '    # Step 4: Return to our app')
if p2a in text:
    text = text.replace(p2a, r2a, 1)
    print('FIX 2a: verify after opening dummy')
else:
    print('FIX 2a: NOT FOUND')

# FIX 3: Verify after returning to target app
pos = 0
found3 = False
while True:
    pos = text.find('run_adb(["shell", "monkey", "-p", target_app', pos)
    if pos == -1:
        break
    snippet = text[pos:pos+400]
    if 'time.sleep(2.5)' in snippet and '# Step 5: Check screen' in snippet:
        start = text.rfind(le, 0, pos) + len(le)
        step5_pos = text.find('# Step 5: Check screen', pos)
        end = text.find(le, step5_pos) + len(le)
        old_sec = text[start:end]
        new_sec = ('    run_adb(["shell", "monkey", "-p", target_app, "-c", "android.intent.category.LAUNCHER", "1"])' + le +
                   '    time.sleep(2.5)' + verify_return +
                   '    # Step 5: Check screen according to actual UI elements (No blind forced click)')
        text = text[:start] + new_sec + text[end:]
        print(f'FIX 3: verify after return (pos {start})')
        found3 = True
        break
    pos += 1
if not found3:
    print('FIX 3: NOT FOUND')

# FIX 4: Quiz reset after bypass
for old_p, new_p in [
    ('                perform_fake_install_bypass()' + le + '                return False, "INSTALL_BYPASS_EXECUTED"',
     '                perform_fake_install_bypass()' + le + '                QUIZ_STATE["last_quiz_id"] = None' + le + '                QUIZ_STATE["repeat_count"] = 0' + le + '                return False, "INSTALL_BYPASS_EXECUTED"'),
    ('            perform_fake_install_bypass()' + le + '            return False, "INSTALL_BYPASS_EXECUTED"',
     '            perform_fake_install_bypass()' + le + '            QUIZ_STATE["last_quiz_id"] = None' + le + '            QUIZ_STATE["repeat_count"] = 0' + le + '            return False, "INSTALL_BYPASS_EXECUTED"'),
    ('                perform_fake_install_bypass()' + le + '                return False, "FINAL_WATCH_BYPASS"',
     '                perform_fake_install_bypass()' + le + '                QUIZ_STATE["last_quiz_id"] = None' + le + '                QUIZ_STATE["repeat_count"] = 0' + le + '                return False, "FINAL_WATCH_BYPASS"'),
]:
    if old_p in text:
        text = text.replace(old_p, new_p, 1)
        print(f'FIX 4: quiz reset applied')
        break
else:
    print('FIX 4: NOT FOUND')

# FIX 5: Safe click bounds in Ollama handler
old_oc = ('            if click_x and click_y:' + le +
          '                print(f"? [OLLAMA ACTION] Resolved event popup -> Tapping ({click_x}, {click_y}) | Reason: {reason}", flush=True)' + le +
          '                tap(click_x, click_y)' + le +
          '                time.sleep(2)' + le +
          '                return False, "OLLAMA_EVENT_CLICK"' + le)
new_oc = ('            if click_x and click_y:' + le +
          '                # [SAFE CLICK] Only tap within safe screen bounds' + le +
          '                if 50 <= click_x <= 1030 and 200 <= click_y <= 2200:' + le +
          '                    print(f"? [OLLAMA ACTION] Resolved -> Tapping ({click_x}, {click_y}) | Reason: {reason}", flush=True)' + le +
          '                    tap(click_x, click_y)' + le +
          '                    time.sleep(2)' + le +
          '                    return False, "OLLAMA_EVENT_CLICK"' + le +
          '                else:' + le +
          '                    print(f"? [SAFE CLICK] Out-of-bounds ({click_x}, {click_y}) - skipping.", flush=True)' + le +
          '                    return False, "OLLAMA_SKIPPED_UNSAFE"' + le)
if old_oc in text:
    text = text.replace(old_oc, new_oc, 1)
    print('FIX 5: safe click bounds')
else:
    print('FIX 5: Ollama click pattern NOT FOUND')

# Write
with open(path, 'wb') as f:
    f.write(text.encode('utf-8'))

import py_compile
try:
    py_compile.compile(path, doraise=True)
    print('\n=== SYNTAX OK ===')
except Exception as e:
    print(f'\n=== SYNTAX ERROR: {e} ===')

print(f'Final size: {len(text)} bytes')
