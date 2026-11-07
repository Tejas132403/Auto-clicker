with open('free_ai_bot_reconstructed.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Fix f-strings that use e['text'], e['bounds'], etc.
# These are invalid because backslash escapes don't work inside f-string expressions.
# Replace with e.get("text", "") style or extract to variable first.

replacements = [
    # perform_fake_install_bypass: add bonus found
    (
        "print(f\"\\U0001f3e1 Found \\'{e[\\'text\\']}\\' button -> Tapping ({e[\\'bounds\\'][\\'cx\\']}, {e[\\'bounds\\'][\\'cy\\']})\", flush=True)\n            tap(e[\"bounds\"][\"cx\"], e[\"bounds\"][\"cy\"])",
        "et = e.get(\"text\", \"\"); eb = e.get(\"bounds\", {}); print(f\"\\U0001f3e1 Found \\'{et}\\' button -> Tapping ({eb.get(\\'cx\\', 0)}, {eb.get(\\'cy\\', 0)})\", flush=True)\n            tap(eb.get(\"cx\"), eb.get(\"cy\"))"
    ),
    # perform_fake_install_bypass: dialog button found
    (
        "print(f\"\\u26a1 Found dialog button \\'{e[\\'text\\']}\\' -> Tapping ({e[\\'bounds\\'][\\'cx\\']}, {e[\\'bounds\\'][\\'cy\\']})\", flush=True)\n                tap(e[\"bounds\"][\"cx\"], e[\"bounds\"][\"cy\"])",
        "et = e.get(\"text\", \"\"); eb = e.get(\"bounds\", {}); print(f\"\\u26a1 Found dialog button \\'{et}\\' -> Tapping ({eb.get(\\'cx\\', 0)}, {eb.get(\\'cy\\', 0)})\", flush=True)\n                tap(eb.get(\"cx\"), eb.get(\"cy\"))"
    ),
    # dismiss_ad_if_present: close button found
    (
        "print(f\"\\u274c Found ad close button \\'{e[\\'text\\']}\\' -> Tapping ({e[\\'bounds\\'][\\'cx\\']}, {e[\\'bounds\\'][\\'cy\\']})\", flush=True)\n            tap(e[\"bounds\"][\"cx\"], e[\"bounds\"][\"cy\"])",
        "et = e.get(\"text\", \"\"); eb = e.get(\"bounds\", {}); print(f\"\\u274c Found ad close button \\'{et}\\' -> Tapping ({eb.get(\\'cx\\', 0)}, {eb.get(\\'cy\\', 0)})\", flush=True)\n            tap(eb.get(\"cx\"), eb.get(\"cy\"))"
    ),
    # handle_add_bonus_and_wait: add bonus found
    (
        "print(f\"\\u2192 Found \\'{e[\\'text\\']}\\' button -> Tapping ({e[\\'bounds\\'][\\'cx\\']}, {e[\\'bounds\\'][\\'cy\\']})\", flush=True)\n            tap(e[\"bounds\"][\"cx\"], e[\"bounds\"][\"cy\"])",
        "et = e.get(\"text\", \"\"); eb = e.get(\"bounds\", {}); print(f\"\\u2192 Found \\'{et}\\' button -> Tapping ({eb.get(\\'cx\\', 0)}, {eb.get(\\'cy\\', 0)})\", flush=True)\n            tap(eb.get(\"cx\"), eb.get(\"cy\"))"
    ),
    # handle_add_bonus_and_wait: install task detected
    (
        "print(f\"\\u2192 [INSTALL TASK] Detected install task: {ad_e.get(\\'text\\', \\'\\')} -> Running install bypass BEFORE closing ad...\", flush=True)",
        "print(f\"\\u2192 [INSTALL TASK] Detected install task: {ad_e.get(\\'text\\', \\'\\') or \\'install task\\'} -> Running install bypass BEFORE closing ad...\", flush=True)"
    ),
]

count = 0
for old, new in replacements:
    if old in text:
        text = text.replace(old, new, 1)
        count += 1
        print(f'Fixed: {old[:60]}...')

if count == 0:
    # The strings might be slightly different - let me find them
    for i, line in enumerate(text.split('\n')):
        if "{e[" in line:
            print(f'Line {i+1}: {repr(line[:100])}')

print(f'\nTotal fixes applied: {count}')

with open('free_ai_bot_reconstructed.py', 'w', encoding='utf-8') as f:
    f.write(text)

import py_compile
try:
    py_compile.compile('free_ai_bot_reconstructed.py', doraise=True)
    print('SYNTAX OK')
except Exception as e:
    print(f'SYNTAX ERROR: {e}')
