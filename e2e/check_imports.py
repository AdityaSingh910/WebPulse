"""Find every module the app imports (top-level AND lazy imports inside functions) and check that each
third-party one is installed in the current interpreter. Catches dependencies that used to arrive only
transitively (e.g. Pillow via the removed LLM stack). Usage: python check_imports.py <repo_root>"""
import ast
import importlib.util
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pkg = os.path.join(root, 'changedetectionio')
# Optional on purpose (guarded by try/except or platform markers in requirements.txt)
OPTIONAL = {'jq', 'gevent', 'ctypes', 'winreg', 'resource', 'fcntl', 'termios', 'grp', 'pwd'}

mods = {}
for dirpath, _, files in os.walk(pkg):
    if os.sep + 'tests' in dirpath or '__pycache__' in dirpath:
        continue
    for f in files:
        if not f.endswith('.py'):
            continue
        path = os.path.join(dirpath, f)
        tree = ast.parse(open(path, encoding='utf-8').read(), path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for n in names:
                mods.setdefault(n.split('.')[0], set()).add(os.path.relpath(path, root))

missing = {}
for m in sorted(mods):
    if m == 'changedetectionio' or m in sys.stdlib_module_names or m in OPTIONAL:
        continue
    if importlib.util.find_spec(m) is None:
        missing[m] = sorted(mods[m])
third_party = [m for m in mods if m != 'changedetectionio' and m not in sys.stdlib_module_names]
print(f'IMPORTS: {len(third_party)} third-party modules referenced, {len(missing)} missing')
for m, where in missing.items():
    print(f'  MISSING {m}: {", ".join(where[:4])}')
sys.exit(1 if missing else 0)
