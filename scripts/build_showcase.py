"""Rebuild the two-page comparison using any three static Egyptian fonts.

python scripts/build_showcase.py --font path/to/Noto.ttf --font path/to/NewGardiner.ttf --font path/to/third.ttf
Font files remain local; only the source and final PDF are deliverables.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

from xsr import build_default_registry
from xsr.font_metrics import load_font, tex_font_path
from xsr.renderer import default_renderer, response_filename

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', action='append', type=Path, required=True)
    args = parser.parse_args()
    if len(args.font) != 3:
        parser.error('supply three --font files for the three-column comparison')
    build = ROOT / 'tmp/pdfs/showcase'
    build.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'examples/font-metrics-showcase.tex'
    config = []
    renderer = default_renderer()
    runs = build_default_registry().script_runs(source.read_text(encoding='utf-8'))
    runs = [run for run in runs if run.script]
    for index, path in enumerate(args.font):
        font = load_font(path)
        key = ['One', 'Two', 'Three'][index]
        escapes = {'\\': r'\textbackslash{}', '{': r'\{', '}': r'\}',
                   '$': r'\$', '&': r'\&', '#': r'\#', '%': r'\%',
                   '_': r'\_', '^': r'\textasciicircum{}', '~': r'\textasciitilde{}'}
        name = ''.join(escapes.get(ch, ch) for ch in font.name)
        config += [fr'\newcommand\Font{key}{{\xsrEgyptianFont{{{tex_font_path(path)}}}}}',
                   fr'\newcommand\Name{key}{{{name}}}']
        options = {'font_digest': font.digest, 'font_path': tex_font_path(path)}
        for run in runs:
            filename = response_filename(source.stem, run.script, renderer.backend_version(run.script), run.text, options)
            (build / filename).write_text(renderer.render(run.script, run.text, options), encoding='utf-8')
        print(f'{font.name}: UPEM={font.units_per_em}, MD5={font.digest}')
    (build / 'font-metrics-fonts.tex').write_text('\n'.join(config), encoding='utf-8')
    env = os.environ.copy()
    env['TEXINPUTS'] = str(ROOT / 'tex') + os.pathsep + env.get('TEXINPUTS', '')
    result = subprocess.run(['xelatex', '-no-shell-escape', '-interaction=nonstopmode', '-halt-on-error', str(source)],
                            cwd=build, env=env, capture_output=True, text=True, errors='replace')
    (build / 'build-output.txt').write_text(result.stdout, encoding='utf-8')
    if result.returncode or 'XSR-UNAVAILABLE' in result.stdout or 'Overfull' in result.stdout:
        raise RuntimeError(f'showcase failed; inspect {build / "build-output.txt"}')
    shutil.copy2(build / source.with_suffix('.pdf').name, source.with_suffix('.pdf'))
    print(source.with_suffix('.pdf'))


if __name__ == '__main__':
    main()
