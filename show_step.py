path = r"D:\KING PROJECT\Auto clicker\free_ai_bot.py"
with open(path, 'rb') as f:
    raw = f.read()
text = raw.decode('utf-8')
idx = text.find('def decide_and_execute_step(')
end = text.find('\n\tdef ', idx + 1)
if end == -1:
    end = idx + 5000
func = text[idx:end]
with open('step_func.txt', 'w', encoding='utf-8') as f:
    f.write(func)
lines = func.split('\n')
for i, line in enumerate(lines[:120]):
    out = ''.join(c if ord(c) < 128 else '?' for c in line)
    print(f'{i:3d}: {out}')
