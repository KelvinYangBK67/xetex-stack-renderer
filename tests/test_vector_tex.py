"""Real XeLaTeX/PDF tests for direct SVG, providers and synthetic tofu."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import fitz
import pytest
from xsr.renderer import main
from test_providers import config, FIXTURES

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which('xelatex') is None, reason='XeLaTeX unavailable')


def compile_document(tmp_path, body, preamble='', mode='shell', prepare=False, success=True):
    source = tmp_path/'vector.tex'
    source.write_text('\\documentclass{article}\n'+fr'\usepackage[mode={mode}]{{xetex-stack-renderer}}'
                      +'\n'+preamble+'\n\\begin{document}\n'+body+'\n\\end{document}\n', encoding='utf-8')
    if prepare:
        main(['preprocess', '--input', str(source), '--output-dir', str(tmp_path)])
    env = os.environ.copy()
    env['TEXINPUTS'] = str(ROOT/'tex')+os.pathsep+env.get('TEXINPUTS','')
    env['PYTHONPATH'] = str(ROOT/'src')+os.pathsep+env.get('PYTHONPATH','')
    result = subprocess.run(['xelatex', '-no-shell-escape' if mode == 'preprocess' else '-shell-escape',
                             '-interaction=nonstopmode', '-halt-on-error', source.name], cwd=tmp_path,
                            env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    if success:
        assert result.returncode == 0, result.stdout+result.stderr
        assert 'XSR-UNAVAILABLE' not in result.stdout
        assert 'Missing character:' not in result.stdout
    else:
        assert result.returncode != 0, result.stdout
    return result.stdout+result.stderr


@pytest.mark.parametrize('mode', ['shell','preprocess'])
def test_direct_unicode_geometry_cache_and_change(tmp_path, mode):
    path = tmp_path/'瀛楀舰.svg'
    path.write_bytes((FIXTURES/'square.svg').read_bytes())
    body = r'Before \setbox0=\hbox{\xsrVectorGlyph{瀛楀舰.svg}}\typeout{VECTOR-SIZE=\the\wd0,\the\ht0,\the\dp0}\box0 after. \xsrVectorGlyph{瀛楀舰.svg}'
    output = compile_document(tmp_path, body, mode=mode, prepare=mode=='preprocess')
    assert 'VECTOR-SIZE=10.0pt,10.0pt,0.0pt' in output
    assert len(list(tmp_path.glob('vector.xsr-*.tex'))) == 1
    assert len(list((tmp_path/'.xsr-cache').glob('*.tex'))) == 1
    with fitz.open(tmp_path/'vector.pdf') as pdf:
        assert 'Before' in pdf[0].get_text() and 'after.' in pdf[0].get_text()
        assert len(pdf[0].get_drawings()) == 2
        assert not pdf[0].get_images()
        for drawing in pdf[0].get_drawings():
            assert drawing['rect'].width == pytest.approx(8, abs=.1)
            assert drawing['rect'].height == pytest.approx(8, abs=.1)
    path.write_text('<svg viewBox="0 0 200 200"><path d="M0 0L200 200L0 200Z"/></svg>')
    compile_document(tmp_path, body, mode=mode, prepare=mode=='preprocess')
    assert len(list(tmp_path.glob('vector.xsr-*.tex'))) == 2


@pytest.mark.parametrize('mode', ['shell','preprocess'])
def test_kage_frontend_synthetic_provider(tmp_path, mode):
    config(tmp_path)
    preamble = r'\xsrKageProvider{provider.json}'
    body = r'Before \xsrKageGlyph{test-glyph} \xsrKageGlyph{test-glyph} {\xsrKageStyle{sans}\xsrKageGlyph{second}} after.'
    compile_document(tmp_path, body, preamble, mode, prepare=mode=='preprocess')
    calls = [json.loads(s) for s in (tmp_path/'calls.jsonl').read_text().splitlines()]
    if mode == 'shell':
        assert calls == [{'glyph':'test-glyph','style':'serif','options':{}}, {'glyph':'second','style':'sans','options':{}}]
    else:
        assert len(calls) == 2  # Brace-scoped styles are discovered literally.
        (tmp_path/'provider.json').write_text((tmp_path/'provider.json').read_text())
        compile_document(tmp_path, body, preamble, mode)
        assert len((tmp_path/'calls.jsonl').read_text().splitlines()) == 2
        assert not list(tmp_path.glob('*.req'))
    with fitz.open(tmp_path/'vector.pdf') as pdf:
        assert len(pdf[0].get_drawings()) == 3
        assert not pdf[0].get_images()


@pytest.mark.parametrize('glyph,code', [('missing','MISSING'),('failure','FAILED'),('invalid','SVG')])
def test_provider_tofu_and_strict(tmp_path, glyph, code):
    config(tmp_path)
    body = fr'Before \xsrKageGlyph{{{glyph}}} after'
    output = compile_document(tmp_path, body, r'\xsrKageProvider{provider.json}')
    assert 'XSR-PROVIDER-'+code in output
    with fitz.open(tmp_path/'vector.pdf') as pdf:
        assert pdf[0].get_drawings()
    output = compile_document(tmp_path, body, r'\xsrKageProvider{provider.json}\xsrMissingGlyphPolicy{error}', success=False)
    assert 'XSR-PROVIDER-'+code in output


def test_provider_not_configured(tmp_path):
    output = compile_document(tmp_path, r'\xsrKageGlyph{test-glyph}\xsrKageGlyph{test-glyph}')
    assert 'XSR-PROVIDER-UNAVAILABLE' in output
    output = compile_document(tmp_path, r'\xsrKageGlyph{test-glyph}', r'\xsrMissingGlyphPolicy{error}', success=False)
    assert 'XSR-PROVIDER-UNAVAILABLE' in output


@pytest.mark.parametrize('mode', ['shell','preprocess'])
def test_kss_missing_visible_only(tmp_path, mode):
    font = ROOT/'tmp/fonts/NotoSerifKhitanSmallScript-Regular.ttf'
    preamble = fr'\xsrKhitanDefaultFont{{{font.as_posix()}}}'
    text = chr(0x18B01)+chr(0x16FE4)+chr(0x18CFF)+' '+chr(0x18B02)+chr(0x200B)+chr(0x18B03)
    output = compile_document(tmp_path, fr'Before \xsrKhitanText{{{text}}} after.', preamble, mode, prepare=mode=='preprocess')
    assert 'XSR-GLYPH-MISSING' in output
    assert 'height=2' in output
    response = '\n'.join(p.read_text() for p in tmp_path.glob('vector.xsr-*.tex'))
    assert response.count('xsrKhitanSynthetic') == 1
    if mode == 'shell':
        output = compile_document(tmp_path, fr'\xsrKhitanText{{{chr(0x18CFF)}}}', preamble+r'\xsrMissingGlyphPolicy{error}', success=False)
        assert 'XSR-GLYPH-MISSING' in output


def test_stroke_affine_and_quadratic_pdf(tmp_path):
    (tmp_path/'stroke.svg').write_text('<svg viewBox="0 0 200 200"><g transform="translate(20 20) scale(2 1)"><path fill="none" stroke="black" stroke-width="4" d="M0 0Q40 160 80 0"/></g></svg>')
    compile_document(tmp_path, r'\xsrVectorGlyph{stroke.svg}')
    with fitz.open(tmp_path/'vector.pdf') as pdf:
        drawings = pdf[0].get_drawings()
        assert len(drawings) == 1
        assert drawings[0]['type'] == 's'
        assert drawings[0]['rect'].width == pytest.approx(8, abs=.15)
        assert not pdf[0].get_images()

@pytest.mark.parametrize('mode', ['shell','preprocess'])
def test_egyptian_missing_hv_pdf(tmp_path, mode):
    from test_font_metrics import make_font
    font = tmp_path/'synthetic.ttf'
    make_font(font)
    from fontTools.ttLib import TTFont
    with TTFont(font) as ft:
        for table in ft['cmap'].tables:
            if table.isUnicode():
                table.cmap[32] = 'empty'
        ft.save(font)
    preamble = fr'\xsrEgyptianDefaultFont{{{font.as_posix()}}}'
    text = chr(0x13000)+chr(0x13431)+chr(0x13002)+chr(0x13430)+chr(0x13000)
    output = compile_document(tmp_path, fr'Before \xsrEgyptianText{{{text}}} after.', preamble, mode, prepare=mode=='preprocess')
    assert 'XSR-GLYPH-MISSING' in output
    with fitz.open(tmp_path/'vector.pdf') as pdf:
        assert pdf[0].get_drawings()
        assert not pdf[0].get_images()

@pytest.mark.parametrize('mode', ['shell','preprocess'])
def test_scoped_policy_and_unicode_provider(tmp_path, mode):
    config(tmp_path)
    font = ROOT/'tmp/fonts/NotoSerifKhitanSmallScript-Regular.ttf'
    preamble = fr'\xsrKhitanDefaultFont{{{font.as_posix()}}}\xsrKageProvider{{provider.json}}'
    body = (fr'\xsrKhitanText{{{chr(0x18CFF)}}} '
            + fr'{{\xsrMissingGlyphPolicy{{error}}\xsrKhitanText{{{chr(0x18B01)}}}\xsrKageGlyph{{字形}}}} '
            + r'\xsrKageGlyph{missing}')
    output = compile_document(tmp_path, body, preamble, mode, prepare=mode=='preprocess')
    assert 'XSR-GLYPH-MISSING' in output and 'XSR-PROVIDER-MISSING' in output
    calls = [json.loads(line) for line in (tmp_path/'calls.jsonl').read_text().splitlines()]
    assert [c['glyph'] for c in calls] == ['字形', 'missing']
