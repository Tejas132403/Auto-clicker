import marshal

with open('__pycache__/free_ai_bot.cpython-314.pyc', 'rb') as f:
    f.read(16)
    code = marshal.load(f)

funcs = {}
for const in code.co_consts:
    if hasattr(const, 'co_name') and const.co_name != '<module>':
        funcs[const.co_name] = const

# Module-level strings (imports, config)
print("=== MODULE LEVEL CONSTANTS ===")
for c in code.co_consts:
    if isinstance(c, str) and len(c) > 5:
        print(f'  STR: {c[:120]}')

# Extract strings from each function
for name in sorted(funcs.keys()):
    fc = funcs[name]
    strs = []
    for c in fc.co_consts:
        if isinstance(c, str):
            strs.append(c)
    if strs:
        with open(f'str_{name}.txt', 'w', encoding='utf-8') as f:
            for s in strs:
                f.write(s + '\n')
        print(f'  {name}: {len(strs)} strings -> str_{name}.txt')
    else:
        print(f'  {name}: no strings')
