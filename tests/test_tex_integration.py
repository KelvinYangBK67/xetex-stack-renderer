import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import hieropy


ROOT = Path(__file__).resolve().parents[1]
A = chr(0x13000)
B = chr(0x13050)
C = chr(0x13153)
H = chr(0x13431)
V = chr(0x13430)


def valid_ehfc() -> str:
    return A + H + B


def hieropy_test_font_preamble() -> str:
    font = Path(hieropy.__file__).parent / 'resources' / 'NewGardiner.ttf'
    return fr'\xsrEgyptianFont{{{font.as_posix()}}}'


def with_egyptian_font(text: str) -> str:
    return f'{{{text}}}'


def run_xelatex(
    tmp_path: Path,
    body: str,
    preamble: str = '',
    packages: str = r'\usepackage{xetex-stack-renderer}',
) -> subprocess.CompletedProcess[str]:
    if not preamble:
        preamble = hieropy_test_font_preamble()
    source = tmp_path / 'integration.tex'
    source.write_text(
        '\\documentclass{article}\n'
        f'{packages}\n'
        f'{preamble}\n'
        '\\begin{document}\n'
        f'{body}\n'
        '\\end{document}\n',
        encoding='utf-8',
    )
    env = os.environ.copy()
    env['TEXINPUTS'] = str(ROOT / 'tex') + os.pathsep + env.get('TEXINPUTS', '')
    env['PYTHONPATH'] = str(ROOT / 'src') + os.pathsep + env.get('PYTHONPATH', '')
    return subprocess.run(
        [
            'xelatex',
            '-shell-escape',
            '-interaction=nonstopmode',
            '-halt-on-error',
            source.name,
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )


def assert_real_layout(
    completed: subprocess.CompletedProcess[str], glyphs: int
) -> None:
    assert completed.returncode == 0, completed.stdout
    assert 'XSR-UNAVAILABLE' not in completed.stdout
    assert 'parsed stub' not in completed.stdout
    # NewGardiner has no space glyph; XeTeX probes U+0020 when loading it.
    missing = re.findall(r'Missing character:.*?\(U\+([0-9A-F]+)\)', completed.stdout)
    assert set(missing) <= {'0020'}, completed.stdout
    assert completed.stdout.count('path=real-layout') == 1
    assert f'XSR-LAYOUT script=egyptian glyphs={glyphs}' in completed.stdout


@pytest.mark.skipif(shutil.which('xelatex') is None, reason='xelatex is unavailable')
def test_latin_ehfc_latin_dispatches_one_complete_run(tmp_path: Path) -> None:
    body = f'Latin {with_egyptian_font(valid_ehfc())} Latin'
    completed = run_xelatex(
        tmp_path, body, preamble=hieropy_test_font_preamble()
    )

    assert_real_layout(completed, glyphs=2)
    assert completed.stdout.count('XSR-DISPATCH script=egyptian codepoints=3') == 1
    assert completed.stdout.count('XSR-BACKEND script=egyptian codepoints=3') == 1
    assert 'parser=hieropy-0.1.4' in completed.stdout
    assert (tmp_path / 'integration.pdf').is_file()


@pytest.mark.skipif(shutil.which('xelatex') is None, reason='xelatex is unavailable')
def test_single_sign_real_layout(tmp_path: Path) -> None:
    completed = run_xelatex(
        tmp_path,
        with_egyptian_font(A),
        preamble=hieropy_test_font_preamble(),
    )

    assert_real_layout(completed, glyphs=1)
    assert completed.stdout.count('XSR-DISPATCH script=egyptian codepoints=1') == 1
    assert (tmp_path / 'integration.pdf').is_file()


@pytest.mark.skipif(shutil.which('xelatex') is None, reason='xelatex is unavailable')
def test_horizontal_group_real_layout(tmp_path: Path) -> None:
    completed = run_xelatex(
        tmp_path,
        with_egyptian_font(A + H + B),
        preamble=hieropy_test_font_preamble(),
    )

    assert_real_layout(completed, glyphs=2)
    assert completed.stdout.count('XSR-DISPATCH script=egyptian codepoints=3') == 1
    assert (tmp_path / 'integration.pdf').is_file()


@pytest.mark.skipif(shutil.which('xelatex') is None, reason='xelatex is unavailable')
def test_vertical_group_real_layout(tmp_path: Path) -> None:
    completed = run_xelatex(
        tmp_path,
        with_egyptian_font(A + V + B),
        preamble=hieropy_test_font_preamble(),
    )

    assert_real_layout(completed, glyphs=2)
    assert completed.stdout.count('XSR-DISPATCH script=egyptian codepoints=3') == 1
    assert (tmp_path / 'integration.pdf').is_file()


@pytest.mark.skipif(shutil.which('xelatex') is None, reason='xelatex is unavailable')
def test_nested_hv_group_real_layout(tmp_path: Path) -> None:
    completed = run_xelatex(
        tmp_path,
        with_egyptian_font(A + H + B + V + C),
        preamble=hieropy_test_font_preamble(),
    )

    assert_real_layout(completed, glyphs=3)
    assert completed.stdout.count('XSR-DISPATCH script=egyptian codepoints=5') == 1
    assert (tmp_path / 'integration.pdf').is_file()


@pytest.mark.skipif(shutil.which('xelatex') is None, reason='xelatex is unavailable')
def test_egyptian_before_active_tilde_flushes_in_order(tmp_path: Path) -> None:
    body = (
        '\\begingroup\n'
        '\\def~{\\typeout{XSR-ACTIVE-TILDE}\\nobreakspace}\n'
        f'{chr(0x13000)}~Latin\n'
        '\\endgroup'
    )

    completed = run_xelatex(tmp_path, body)

    assert completed.returncode == 0, completed.stdout
    assert completed.stdout.count('XSR-DISPATCH script=egyptian codepoints=1') == 1
    assert completed.stdout.count('XSR-ACTIVE-TILDE') == 1
    assert completed.stdout.index('XSR-BACKEND') < completed.stdout.index(
        'XSR-ACTIVE-TILDE'
    )


@pytest.mark.skipif(shutil.which('xelatex') is None, reason='xelatex is unavailable')
def test_multiple_egyptian_runs_dispatch_separately(tmp_path: Path) -> None:
    body = f'{chr(0x13000)} Latin {chr(0x13001)}'

    completed = run_xelatex(tmp_path, body)

    assert completed.returncode == 0, completed.stdout
    assert completed.stdout.count('XSR-DISPATCH script=egyptian codepoints=1') == 2
    assert completed.stdout.count('XSR-BACKEND script=egyptian codepoints=1') == 2
    assert len(list(tmp_path.glob('integration.xsr-*.tex'))) == 2


@pytest.mark.skipif(shutil.which('xelatex') is None, reason='xelatex is unavailable')
def test_host_can_dispatch_complete_run_without_loading_detector(tmp_path: Path) -> None:
    body = (
        r'\ExplSyntaxOn'
        fr'\xsr_dispatch_run:nn{{egyptian}}{{{valid_ehfc()}}}'
        r'\ExplSyntaxOff'
    )
    packages = '\\usepackage{xsr-core}\n\\usepackage{xsr-egyptian}'

    completed = run_xelatex(tmp_path, body, packages=packages)

    assert completed.returncode == 0, completed.stdout
    assert completed.stdout.count('XSR-DISPATCH script=egyptian codepoints=3') == 1
    assert 'xsr-detector-active.sty' not in completed.stdout

@pytest.mark.skipif(shutil.which('xelatex') is None, reason='xelatex is unavailable')
def test_actual_font_file_cross_font(tmp_path, font):
    preamble = fr'\xsrEgyptianFont{{{font.path.as_posix()}}}'
    completed = run_xelatex(tmp_path, A + H + chr(0x13437) + B + V + C + chr(0x13438), preamble)
    assert_real_layout(completed, 3)
    response, = tmp_path.glob('integration.xsr-*.tex')
    assert font.digest in response.read_text()
    assert font.path.name in response.read_text()
    if shutil.which('pdffonts'):
        report = subprocess.check_output(['pdffonts', str(tmp_path / 'integration.pdf')], text=True)
        assert font._font['name'].getDebugName(6) in report


@pytest.mark.skipif(shutil.which('xelatex') is None, reason='xelatex is unavailable')
def test_preprocessed_font_response_and_scoped_switch(tmp_path):
    from conftest import FONTS
    from xsr.font_metrics import load_font, tex_font_path
    from xsr.renderer import default_renderer, response_filename
    renderer = default_renderer()
    text = A + V + B
    body = []
    for path in FONTS:
        font = load_font(path)
        options = {'font_digest': font.digest, 'font_path': tex_font_path(path)}
        name = response_filename('integration', 'egyptian', renderer.backend_version('egyptian'), text, options)
        (tmp_path / name).write_text(renderer.render('egyptian', text, options), encoding='utf-8')
        body.append(fr'{{\xsrEgyptianFont{{{tex_font_path(path)}}}{text}}}')
    result = run_xelatex(tmp_path, ' Latin '.join(body), packages=r'\usepackage[mode=preprocess]{xetex-stack-renderer}')
    assert result.returncode == 0, result.stdout
    assert result.stdout.count('path=real-layout') == len(FONTS)
    assert 'XSR-UNAVAILABLE' not in result.stdout
    assert not list(tmp_path.glob('*.req'))

@pytest.mark.skipif(shutil.which('xelatex') is None, reason='xelatex is unavailable')
def test_outline_bearings_and_descender_render_inside_box(tmp_path):
    fitz = pytest.importorskip('fitz', reason='PyMuPDF enables raster ink verification')
    from test_font_metrics import make_font
    path = tmp_path / 'font with spaces.ttf'
    make_font(path)
    preamble = (fr'\xsrEgyptianFont{{{path.as_posix()}}}'
                + r'\usepackage{xcolor}\pagestyle{empty}\setlength\fboxsep{0pt}')
    result = run_xelatex(tmp_path, r'\noindent{\fontsize{100}{120}\selectfont\fcolorbox{blue}{white}{' + A + '}}', preamble)
    assert_real_layout(result, 1)
    with fitz.open(tmp_path / 'integration.pdf') as pdf:
        pix = pdf[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        samples = pix.samples
        black, blue = [], []
        for y in range(pix.height):
            for x in range(pix.width):
                offset = (y * pix.width + x) * 3
                r, g, b = samples[offset:offset + 3]
                if max(r, g, b) < 50:
                    black.append((x, y))
                if b > r + 50 and b > g + 50:
                    blue.append((x, y))
        def bounds(points):
            assert points
            return min(x for x,y in points), min(y for x,y in points), max(x for x,y in points), max(y for x,y in points)
        ink, frame = bounds(black), bounds(blue)
        assert frame[0] < ink[0] < ink[2] < frame[2]
        assert frame[1] < ink[1] < ink[3] < frame[3]
        # The response must not add a trailing interword space to the box.
        assert frame[2] - frame[0] == pytest.approx(.68 * 100 * 72 / 72.27 * 2, abs=3)
        # TeX points to PDF points, at 2 pixels per PDF point.
        assert ink[2] - ink[0] == pytest.approx(.6 * 100 * 72 / 72.27 * 2, abs=2)
        assert ink[3] - ink[1] == pytest.approx(.9 * 100 * 72 / 72.27 * 2, abs=2)


@pytest.mark.skipif(shutil.which('xelatex') is None, reason='xelatex is unavailable')
def test_stale_preprocessed_response_rejected_by_tex(tmp_path):
    from test_font_metrics import make_font
    from xsr.renderer import default_renderer
    path = tmp_path / 'font.ttf'
    make_font(path)
    response = default_renderer().render('egyptian', A, {'font_path': str(path)})
    (tmp_path / 'stale.tex').write_text(response, encoding='utf-8')
    make_font(path, width=800)
    result = run_xelatex(tmp_path, r'\input{stale.tex}')
    assert result.returncode != 0
    assert 'font file changed' in result.stdout
