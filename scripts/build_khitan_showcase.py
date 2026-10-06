"""Build the Khitan showcase with optional external-font comparison."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from xsr import build_default_registry
from xsr.errors import XSRError
from xsr.font_metrics import load_font, font_options, tex_font_path
from xsr.renderer import default_renderer, request_digest
from xsr.bundle import write_bundle

ROOT = Path(__file__).resolve().parents[1]


def khitan_runs(source):
    return {run.text for run in build_default_registry().script_runs(source)
            if run.script == 'khitan'}


def prepare(renderer, responses, font, runs):
    options = font_options(font.path) | {'cluster_gap': 0.2}
    count = 0
    for text in sorted(runs):
        try:
            response = renderer.render('khitan', text, options)
        except XSRError as error:
            if error.code == 'XSR-GLYPH-MISSING':
                # An optional comparison font can cover a sign absent in Noto.
                continue
            raise
        digest = request_digest('khitan',
                                 renderer.backend_version('khitan'), text, options)
        responses[digest] = response
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', type=Path, required=True, help='Noto reference font')
    parser.add_argument('--comparison-font', type=Path,
                        help='optional second local outline font')
    parser.add_argument('--source', type=Path, default=ROOT/'examples/khitan-showcase.tex')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    noto = load_font(args.font)
    linear = load_font(args.comparison_font) if args.comparison_font else None
    source = args.source.resolve()
    output = (args.output or source.with_suffix('.pdf')).resolve()
    scratch = ROOT/'tmp/pdfs'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='khitan-showcase-', dir=scratch) as directory:
        build = Path(directory)
        spelling = tex_font_path(noto.path)
        config = (fr'\xsrKhitanDefaultFont{{{spelling}}}' + '\n'
                  + fr'\newcommand\NotoSelect{{\xsrKhitanFont{{{spelling}}}}}' + '\n'
                  + fr'\font\KhitanNative="[{spelling}]:+rclt" at 12pt' + '\n')
        if linear:
            other = tex_font_path(linear.path)
            config += fr'\newcommand\LinearSelect{{\xsrKhitanFont{{{other}}}}}' + '\n'
            extra = (ROOT/'examples/khitan-linear-comparison.tex').read_text(encoding='utf-8')
        else:
            extra = ''
        (build/'khitan-showcase-fonts.tex').write_text(config, encoding='utf-8')
        (build/'khitan-extra.tex').write_text(extra, encoding='utf-8')
        renderer = default_renderer()
        responses = {}
        runs = khitan_runs(source.read_text(encoding='utf-8') + extra)
        count = prepare(renderer, responses, noto, runs)
        if linear:
            count += prepare(renderer, responses, linear, khitan_runs(extra))
        write_bundle(build, source.stem, responses)
        env = os.environ.copy()
        env['TEXINPUTS'] = str(ROOT/'tex')+os.pathsep+env.get('TEXINPUTS', '')
        result = subprocess.run(
            ['xelatex', '-no-shell-escape', '-interaction=nonstopmode',
             '-halt-on-error', str(source)],
            cwd=build, env=env, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=120)
        (scratch/'khitan-showcase-build.log').write_text(result.stdout, encoding='utf-8')
        if result.returncode or 'XSR-UNAVAILABLE' in result.stdout or 'Overfull' in result.stdout:
            raise RuntimeError(f'Khitan showcase failed; inspect {scratch / "khitan-showcase-build.log"}')
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(build/source.with_suffix('.pdf').name, output)
    names = noto.name + (f' / {linear.name}' if linear else '')
    print(f'{output}: {count} responses; {names}')


if __name__ == '__main__':
    main()