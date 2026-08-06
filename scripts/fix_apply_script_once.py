#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).with_name("apply_accessibility_checks_once.py")
text = path.read_text(encoding="utf-8")
old = '''        box = box.replace("      <div\\n", "      <section\\n", 1)
        box = box.replace('        role="dialog"\\n', "", 1)
        box = box.replace('        tabindex="-1"\\n', "", 1)
        box = box.replace('href="#hospital"', f'href="#{thumb_id}"')
        box = box[:-len("      </div>\\n")] + "      </section>\\n"
'''
new = '''        box = box.replace('        role="dialog"\\n', '        role="region"\\n', 1)
        box = box.replace('        tabindex="-1"\\n', "", 1)
        box = box.replace('href="#hospital"', f'href="#{thumb_id}"')
'''
if text.count(old) != 1:
    raise SystemExit("Temporary apply script transformation block not found exactly once")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
