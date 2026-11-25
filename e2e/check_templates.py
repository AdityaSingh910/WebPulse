"""Syntax-check every Jinja2 template in the app (catches broken {% %} blocks / quoting after edits).
Usage: python check_templates.py <repo_root>   -> exit 1 on any parse error."""
import glob
import os
import sys

import jinja2

root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env = jinja2.Environment(extensions=['jinja2.ext.i18n', 'jinja2.ext.do', 'jinja2.ext.loopcontrols'])
files = [f for f in glob.glob(os.path.join(root, 'changedetectionio', '**', '*.html'), recursive=True)
         if os.sep + 'tests' + os.sep not in f]
errors = 0
for f in files:
    try:
        env.parse(open(f, encoding='utf-8').read())
    except jinja2.TemplateSyntaxError as e:
        errors += 1
        print(f'TEMPLATE ERROR {os.path.relpath(f, root)}:{e.lineno}: {e.message}')
print(f'TEMPLATES: {len(files)} parsed, {errors} syntax errors')
sys.exit(1 if errors else 0)
