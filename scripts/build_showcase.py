"""Build a clean two- or three-font visual comparison without shell escape."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from xsr import build_default_registry
from xsr.egyptian.source import source_runs
from xsr.font_metrics import load_font, tex_font_path, font_options
from xsr.renderer import default_renderer, response_filename

ROOT=Path(__file__).resolve().parents[1]


def escape_tex(value):
    escapes={'\\':r'\textbackslash{}','{':r'\{','}':r'\}','$':r'\$',
             '&':r'\&','#':r'\#','%':r'\%','_':r'\_','^':r'\textasciicircum{}','~':r'\textasciitilde{}'}
    return ''.join(escapes.get(ch,ch) for ch in value)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font',action='append',type=Path,required=True)
    parser.add_argument('--source',type=Path,default=ROOT/'examples/egyptian-showcase.tex')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if len(args.font) not in (2,3):
        parser.error('supply two or three --font files')
    source=args.source.resolve()
    output=(args.output or source.with_suffix('.pdf')).resolve()
    scratch=ROOT/'tmp/pdfs'
    scratch.mkdir(parents=True,exist_ok=True)
    # A fresh, owned temporary directory prevents success through stale responses.
    with tempfile.TemporaryDirectory(prefix='showcase-',dir=scratch) as directory:
        build=Path(directory)
        config=[fr'\newcommand\XSRFontCount{{{len(args.font)}}}']
        renderer=default_renderer(build/'.xsr-cache')
        runs={run.text for run in source_runs(source.read_text(encoding='utf-8'),build_default_registry())}
        for index,path in enumerate(args.font):
            font=load_font(path)
            key=['One','Two','Three'][index]
            config += [fr'\newcommand\Font{key}{{\xsrEgyptianFont{{{tex_font_path(path)}}}}}',
                       fr'\newcommand\Name{key}{{{escape_tex(font.name)}}}']
            for direction in ('ltr','rtl'):
                options=font_options(path) | ({'direction':'rtl'} if direction=='rtl' else {})
                for text in sorted(runs):
                    name=response_filename(source.stem,'egyptian',renderer.backend_version('egyptian'),text,options)
                    (build/name).write_text(renderer.render('egyptian',text,options),encoding='utf-8')
            print(f'{font.name}: UPEM={font.units_per_em}, MD5={font.digest}')
        for name in ('showcase-fonts.tex','font-metrics-fonts.tex'):
            (build/name).write_text('\n'.join(config),encoding='utf-8')
        env=os.environ.copy()
        env['TEXINPUTS']=str(ROOT/'tex')+os.pathsep+env.get('TEXINPUTS','')
        result=subprocess.run(['xelatex','-no-shell-escape','-interaction=nonstopmode','-halt-on-error',str(source)],
                              cwd=build,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
        (scratch/'showcase-build.log').write_text(result.stdout,encoding='utf-8')
        import re
        missing=re.findall(r'Missing character:.*?\(U\+([0-9A-F]+)\)',result.stdout)
        if result.returncode or 'XSR-UNAVAILABLE' in result.stdout or 'Overfull' in result.stdout or set(missing)-{'0020'}:
            raise RuntimeError(f'showcase failed; inspect {scratch / "showcase-build.log"}')
        output.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(build/source.with_suffix('.pdf').name,output)
    print(output)


if __name__=='__main__':
    main()
