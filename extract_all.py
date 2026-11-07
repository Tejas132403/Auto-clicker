import marshal, os

with open('__pycache__/free_ai_bot.cpython-314.pyc', 'rb') as f:
    f.read(16)
    code = marshal.load(f)

funcs = {}
for const in code.co_consts:
    if hasattr(const, 'co_name') and const.co_name != '<module>':
        funcs[const.co_name] = const

os.makedirs('pyc_strings', exist_ok=True)

# Module constants
with open('pyc_strings/module.txt', 'wb') as f:
    for c in code.co_consts:
        if isinstance(c, str):
            f.write(c.encode('utf-8') + b'\n')
    for c in code.co_consts:
        if isinstance(c, (int, float, bool, type(None))):
            f.write(str(c).encode('utf-8') + b'\n')

# Each function's strings and bytecode info
for name, fc in sorted(funcs.items()):
    with open(f'pyc_strings/{name}.txt', 'wb') as f:
        f.write(f'=== {name} (line {fc.co_firstlineno}, args={fc.co_argcount}) ===\n'.encode())
        f.write(f'varnames: {fc.co_varnames}\n'.encode())
        f.write(f'consts count: {len(fc.co_consts)}\n'.encode())
        for c in fc.co_consts:
            if isinstance(c, str):
                f.write(b'STR: ' + c.encode('utf-8') + b'\n')
            elif isinstance(c, (int, float, bool, type(None))):
                f.write(b'VAL: ' + str(c).encode('utf-8') + b'\n')
        # Also get the line number table
        if hasattr(fc, 'co_lines'):
            lines = list(fc.co_lines())
            f.write(b'lines: ' + str(lines[:20]).encode('utf-8') + b'\n')
