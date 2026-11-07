path = r"D:\KING PROJECT\Auto clicker\free_ai_bot.py"
with open(path, 'rb') as f:
    raw = f.read()
text = raw.decode('utf-8')
idx = text.find('def perform_fake_install_bypass(')
end = text.find('\ndef ', idx + 1)
if end == -1:
    end = idx + 3000
func = text[idx:end]
# Write to file to avoid encoding issues
with open('bypass_func.txt', 'w', encoding='utf-8') as f:
    f.write(func)
print(f'Wrote {len(func)} chars')
# Print safe version
for i, line in enumerate(func.split('\n')):
    out = ''.join(c if ord(c) < 128 else '?' for c in line)
    print(f'{i:3d}: {out}')
