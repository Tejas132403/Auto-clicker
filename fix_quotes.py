with open('free_ai_bot_reconstructed.py', 'r', encoding='utf-8') as f:
    text = f.read()

count = text.count("\\'")
text = text.replace("\\'", "'")
print(f"Replaced {count} backslashed quotes")

with open('free_ai_bot_reconstructed.py', 'w', encoding='utf-8') as f:
    f.write(text)

import py_compile
try:
    py_compile.compile('free_ai_bot_reconstructed.py', doraise=True)
    print('SYNTAX OK')
except Exception as e:
    print(f'SYNTAX ERROR: {e}')
