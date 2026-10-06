"""Build the three-page external-vector showcase using only synthetic SVG."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from xsr.renderer import main as render_main

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--khitan-font', type=Path, default=ROOT/'tmp/fonts/NotoSerifKhitanSmallScript-Regular.ttf')
    parser.add_argument('--egyptian-font', type=Path, default=ROOT/'tmp/fonts/NotoSansEgyptianHieroglyphs-Regular.ttf')
    parser.add_argument('--output', type=Path, default=ROOT/'examples/vector-showcase.pdf')
    args = parser.parse_args()
    scratch = ROOT/'tmp/pdfs'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='vector-showcase-', dir=scratch) as directory:
        build = Path(directory).resolve()
        shutil.copy2(ROOT/'examples/vector-showcase.tex', build/'vector-showcase.tex')
        shutil.copy2(ROOT/'tests/fixtures/square.svg', build/'square.svg')
        assets = {
            'curve': 'M20 180 Q100 -80 180 180 L155 180 Q100 20 45 180 Z',
            'diamond': 'M100 15 L185 100 L100 185 L15 100 Z M100 45 L45 100 L100 155 L155 100 Z',
            'sparse': 'M85 85 H115 V115 H85 Z',
        }
        for name, path in assets.items():
            transform = ' transform="rotate(12 100 100)"' if name == 'diamond' else ''
            (build/(name+'.svg')).write_text(f'<svg viewBox="0 0 200 200"><path d="{path}"{transform}/></svg>', encoding='utf-8')
        (build/'provider.json').write_text(json.dumps({
            'executable': sys.executable,
            'prefix_args': [str(ROOT/'tests/fixtures/synthetic_provider.py'), '--log', str(build/'calls.jsonl')],
            'metadata': {'engine_version': 'synthetic-1', 'dataset_version': 'none'}}), encoding='utf-8')
        (build/'vector-showcase-config.tex').write_text(
            r'\xsrKageProvider{provider.json}'+'\n'
            + fr'\xsrKhitanDefaultFont{{{args.khitan_font.resolve().as_posix()}}}'+'\n'
            + fr'\xsrEgyptianDefaultFont{{{args.egyptian_font.resolve().as_posix()}}}'+'\n', encoding='utf-8')
        render_main(['preprocess', '--input', str(build/'vector-showcase.tex'), '--output-dir', str(build)])
        before = (build/'calls.jsonl').read_bytes()
        env = os.environ.copy()
        env['TEXINPUTS'] = str(ROOT/'tex')+os.pathsep+env.get('TEXINPUTS','')
        result = subprocess.run(['xelatex','-no-shell-escape','-interaction=nonstopmode','-halt-on-error','vector-showcase.tex'],
                                cwd=build, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
        (scratch/'vector-showcase-build.log').write_text(result.stdout+result.stderr, encoding='utf-8')
        if result.returncode or 'Overfull' in result.stdout or 'XSR-UNAVAILABLE' in result.stdout or 'Missing character:' in result.stdout:
            raise RuntimeError(f'vector showcase failed; inspect {scratch}/vector-showcase-build.log')
        assert before == (build/'calls.jsonl').read_bytes(), 'provider ran during final compilation'
        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(build/'vector-showcase.pdf', args.output)
    print(args.output)


if __name__ == '__main__':
    main()
