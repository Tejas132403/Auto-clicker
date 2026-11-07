with open('free_ai_bot.py', 'rb') as f:
    data = f.read()

# Fix: replace \x8f byte with the correct UTF-8 sequence
# \xe2\x8f\xb3 is the UTF-8 for ⏳ (U+23F3)
# But there's a stray \x8f byte that should be part of a multibyte sequence
# Let me find all problematic bytes and fix them

# Actually the issue is simpler - the \x8f is a orphaned continuation byte
# It should be \xe2\x8f\xb3 (⏳) but got truncated
# Let me find all such issues

# Replace orphaned continuation bytes
fixed = bytearray(data)
changes = 0
i = 0
while i < len(fixed):
    b = fixed[i]
    # Check for orphaned continuation bytes (0x80-0xBF not preceded by start byte)
    if 0x80 <= b <= 0xBF:
        # Check if previous byte is a UTF-8 start byte
        if i == 0 or not (0xC0 <= fixed[i-1] <= 0xFD):
            # This is an orphaned continuation byte - replace with space
            fixed[i] = 0x20  # space
            changes += 1
    i += 1

if changes > 0:
    print(f"Fixed {changes} orphaned bytes")
    with open('free_ai_bot.py', 'wb') as f:
        f.write(fixed)
else:
    print("No orphaned bytes found")

# Verify
import py_compile
try:
    py_compile.compile('free_ai_bot.py', doraise=True)
    print('SYNTAX OK')
except Exception as e:
    print(f'SYNTAX ERROR: {e}')
