"""End-to-end Khitan XeLaTeX coverage with the official Noto reference font."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import fitz
import pytest

from xsr.renderer import main

ROOT = Path(__file__).resolve().parents[1]
FONT = Path(os.environ.get('XSR_KHITAN_FONT',
             ROOT / 'tmp/fonts/NotoSerifKhitanSmallScript-Regular.ttf'))
A, B, C = (chr(cp) for cp in (0x18B01, 0x18B02, 0x18B03))
F, Z = chr(0x16FE4), chr(0x200B)
AVAILABLE = shutil.which('xelatex') is not None and FONT.is_file()
requires_tex = pytest.mark.skipif(not AVAILABLE, reason='XeLaTeX or Noto KSS font unavailable')


def compile_tex(tmp_path, body, preamble='', mode='shell', shell=True, prepare=False):
    if prepare:
        mode, shell = 'preprocess', False
    source = tmp_path / 'integration.tex'
    preamble = preamble or fr'\xsrKhitanDefaultFont{{{FONT.as_posix()}}}'
    source.write_text(
        '\\documentclass{article}\n'
        + fr'\usepackage[mode={mode}]{{xetex-stack-renderer}}' + '\n'
        + preamble + '\n\\begin{document}\n'
        + body + '\n\\end{document}\n', encoding='utf-8')
    if prepare:
        main(['preprocess','--input',str(source),'--output-dir',str(tmp_path)])
    env = os.environ.copy()
    env['TEXINPUTS'] = str(ROOT / 'tex') + os.pathsep + env.get('TEXINPUTS', '')
    env['PYTHONPATH'] = str(ROOT / 'src') + os.pathsep + env.get('PYTHONPATH', '')
    result = subprocess.run(
        ['xelatex', '-shell-escape' if shell else '-no-shell-escape',
         '-interaction=nonstopmode', '-halt-on-error', source.name],
        cwd=tmp_path, env=env, text=True, encoding='utf-8', errors='replace',
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    assert result.returncode == 0, result.stdout
    assert 'XSR-UNAVAILABLE' not in result.stdout
    return result.stdout, tmp_path / 'integration.pdf'


@requires_tex
@pytest.mark.parametrize('length', range(1, 9))
def test_type_a_lengths_are_atomic_boxes(tmp_path, length):
    output, pdf = compile_tex(tmp_path, fr'Before \xsrKhitanText{{{A*length}}} after.')
    assert f'XSR-LAYOUT script=khitan glyphs={length}' in output
    assert 'XSR-DISPATCH script=khitan codepoints=' in output
    assert pdf.is_file()
    assert 'Overfull' not in output


@requires_tex
@pytest.mark.parametrize('length', range(2, 9))
def test_type_b_lengths(tmp_path, length):
    output, _ = compile_tex(tmp_path, fr'Before \xsrKhitanText{{{A+F+B*(length-1)}}} after.')
    assert f'XSR-LAYOUT script=khitan glyphs={length}' in output
    assert f'codepoints={length+1}' in output
    assert 'Missing character:' not in output
    if length == 8:
        assert 'height=5' in output


@requires_tex
@pytest.mark.parametrize(('separator', 'gap'), [(' ', '0.2'), (Z, '0')])
def test_separator_gap_and_single_dispatch(tmp_path, separator, gap):
    output, _ = compile_tex(tmp_path, fr'Latin \xsrKhitanText{{{A+B+separator+A+B}}} Latin',prepare=True)
    assert output.count('XSR-LAYOUT script=khitan glyphs=2') == 2
    assert output.count('XSR-DISPATCH script=khitan') == 1
    responses = list(tmp_path.glob('.xsr/integration.responses.tex'))
    assert any(fr'\xsrKhitanBreak{{{gap}}}' in p.read_text(encoding='utf-8')
               for p in responses)


@requires_tex
def test_auto_detector_preserves_internal_space_and_latin_neighbors(tmp_path):
    output, _ = compile_tex(tmp_path, f'Latin {A+B} {A+B} end.')
    assert output.count('XSR-DISPATCH script=khitan codepoints=5') == 1
    assert output.count('XSR-LAYOUT script=khitan glyphs=2') == 2


@requires_tex
def test_custom_gap_and_scoped_font(tmp_path):
    preamble = fr'\xsrKhitanDefaultFont{{{FONT.as_posix()}}}'
    body = fr'{{\xsrKhitanClusterGap{{0.35}}\xsrKhitanFont{{{FONT.as_posix()}}}\xsrKhitanText{{{A} {B}}}}}'
    output, _ = compile_tex(tmp_path, body, preamble=preamble,prepare=True)
    assert r'\xsrKhitanBreak{0.35}' in '\n'.join(
        p.read_text(encoding='utf-8') for p in tmp_path.glob('.xsr/integration.responses.tex'))
    assert 'XSR-LAYOUT script=khitan glyphs=1' in output


@requires_tex
def test_unicode_font_path(tmp_path):
    unicode_path = tmp_path / '契丹字型.ttf'
    shutil.copyfile(FONT, unicode_path)
    output, _ = compile_tex(tmp_path, fr'\xsrKhitanText{{{A+B}}}',
                            preamble=fr'\xsrKhitanFont{{{unicode_path.as_posix()}}}')
    assert 'XSR-LAYOUT script=khitan glyphs=2' in output


@requires_tex
def test_preprocess_space_and_zwsp(tmp_path):
    body = fr'\xsrKhitanText{{{A+B} {A+F+B}{Z}{A+B}}}'
    source = tmp_path / 'integration.tex'
    source.write_text('\\documentclass{article}\n'
                      '\\usepackage[mode=preprocess]{xetex-stack-renderer}\n'
                      + fr'\xsrKhitanDefaultFont{{{FONT.as_posix()}}}' + '\n'
                      + '\\begin{document}\n' + body + '\n\\end{document}\n',
                      encoding='utf-8')
    assert main(['preprocess', '--input', str(source), '--output-dir', str(tmp_path)]) == 0
    output, _ = compile_tex(tmp_path, body, mode='preprocess', shell=False)
    assert output.count('XSR-LAYOUT script=khitan') == 3
    assert 'XSR-UNAVAILABLE' not in output


@requires_tex
def test_tall_cluster_only_expands_containing_line(tmp_path):
    body = (r'\setlength{\parindent}{0pt}'
            + 'Line one\\par Line two\\par Line three '
            + fr'\xsrKhitanText{{{A*8}}}'
            + r'\par Line four\par Line five')
    output, pdf = compile_tex(tmp_path, body)
    assert 'XSR-LAYOUT script=khitan glyphs=8 width=2 height=4 depth=0' in output
    with fitz.open(pdf) as document:
        words = document[0].get_text('words')
    ys = {}
    for x0, y0, x1, y1, word, *_ in words:
        if word in {'one', 'two', 'three', 'four', 'five'}:
            ys[word] = y0
    assert len(ys) == 5, ys
    ordinary = ys['two'] - ys['one']
    assert ys['three'] - ys['two'] > ordinary * 2
    assert abs((ys['five'] - ys['four']) - ordinary) < 2


@requires_tex
def test_break_opportunity_between_atomic_clusters(tmp_path):
    body = fr'\parbox{{2.05em}}{{\xsrKhitanText{{{A+B} {A+B}}}}}'
    output, pdf = compile_tex(tmp_path, body)
    assert 'Overfull' not in output
    assert output.count('XSR-LAYOUT script=khitan glyphs=2') == 2
    assert pdf.is_file()

@requires_tex
def test_linear_font_and_missing_sign(tmp_path):
    linear = Path(os.environ.get('XSR_LINEAR_FONT',
                  'D:/_INBOX/Download/KhitanSmallLinear.ttf'))
    if not linear.is_file():
        pytest.skip('local Khitan Small Linear font unavailable')
    missing = chr(0x18CFF)
    output, _ = compile_tex(
        tmp_path, fr'Linear \xsrKhitanText{{{A+missing}}}',
        preamble=fr'\xsrKhitanDefaultFont{{{linear.as_posix()}}}')
    assert 'XSR-LAYOUT script=khitan glyphs=2' in output
    assert 'Missing character:' not in output

@requires_tex
def test_auto_detector_type_b_and_zwsp(tmp_path):
    body = f'Latin {A+F+B}{Z}{A+B} end.'
    output, _ = compile_tex(tmp_path, body,prepare=True)
    assert output.count('XSR-DISPATCH script=khitan codepoints=6') == 1
    assert output.count('XSR-LAYOUT script=khitan glyphs=2') == 2
    assert any(r'\xsrKhitanBreak{0}' in p.read_text(encoding='utf-8')
               for p in tmp_path.glob('.xsr/integration.responses.tex'))


@requires_tex
def test_cluster_cannot_break_internally(tmp_path):
    output, pdf = compile_tex(tmp_path,
        fr'\parbox{{1em}}{{\xsrKhitanText{{{A+B}}}}}')
    assert 'Overfull' in output
    assert output.count('XSR-LAYOUT script=khitan glyphs=2') == 1
    assert pdf.is_file()