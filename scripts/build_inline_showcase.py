"""Build four inline-glyph pages from original neutral fixture drawings."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from xsr.renderer import main as render_main

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from fixtures.inline_assets import make_asset


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'examples/inline-glyph-showcase.pdf')
    args=parser.parse_args()
    scratch=ROOT/'tmp/pdfs';scratch.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='inline-showcase-',dir=scratch) as directory:
        build=Path(directory).resolve()
        source=build/'inline-glyph-showcase.tex'
        shutil.copy2(ROOT/'examples'/source.name,source)
        for name,w,h in [('square',120,120),('tall',120,240),('very-tall',120,480),('wide',240,120),('very-wide',480,120)]:
            make_asset(build/(name+'.png'),w,h)
        for extension in ('jpg','pdf','svg'):
            make_asset(build/('square.'+extension))
        render_main(['preprocess','--input',str(source),'--output-dir',str(build)])
        env=os.environ.copy();env['TEXINPUTS']=str(ROOT/'tex')+os.pathsep+env.get('TEXINPUTS','')
        result=subprocess.run(['xelatex','-no-shell-escape','-interaction=nonstopmode','-halt-on-error',source.name],
                              cwd=build,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
        log=result.stdout+result.stderr
        (scratch/'inline-glyph-showcase-build.log').write_text(log,encoding='utf-8')
        if result.returncode or any(message in log for message in ('Overfull','XSR-UNAVAILABLE','Missing character:')):
            raise RuntimeError(f'inline showcase failed; inspect {scratch}/inline-glyph-showcase-build.log')
        assert not list(build.glob('*.req')), 'unexpected renderer request during final compilation'
        args.output.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source.with_suffix('.pdf'),args.output)
    print(args.output)


if __name__=='__main__':
    main()
