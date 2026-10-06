"""Synthetic protocol fixture, not a KAGE implementation."""
import argparse
import json
from pathlib import Path
import sys
p = argparse.ArgumentParser()
p.add_argument('--glyph', required=True)
p.add_argument('--style', required=True)
p.add_argument('--output', required=True)
p.add_argument('--options-json', default='{}')
p.add_argument('--log')
a = p.parse_args()
if a.log:
    with Path(a.log).open('a', encoding='utf-8') as f:
        f.write(json.dumps({'glyph': a.glyph, 'style': a.style, 'options': json.loads(a.options_json)}, ensure_ascii=True)+'\n')
if a.glyph == 'missing':
    sys.exit(3)
if a.glyph == 'failure':
    sys.exit(7)
if a.glyph == 'empty':
    sys.exit(0)
if a.glyph == 'invalid':
    Path(a.output).write_text('<svg><script/></svg>')
else:
    thickness = 18 if a.style == 'sans' else 10
    path = (f'M20 20 H180 V{20+thickness} H{105+thickness} V180 H95 V{20+thickness} H20 Z'
            if a.glyph != 'second' else 'M100 15 L185 100 L100 185 L15 100 Z M100 45 L45 100 L100 155 L155 100 Z')
    Path(a.output).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><path d="{path}"/></svg>')
