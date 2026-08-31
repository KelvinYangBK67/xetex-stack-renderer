import os
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
    directory = font.parent.as_posix() + '/'
    return (
        r'\usepackage{fontspec}'
        + '\n'
        + fr'\newfontfamily\xsregyptianfont[Path={{{directory}}}]'
        + r'{NewGardiner.ttf}'
    )


def with_egyptian_font(text: str) -> str:
    return f'{{\\xsregyptianfont {text}}}'


def run_xelatex(
    tmp_path: Path,
    body: str,
    preamble: str = '',
    packages: str = r'\usepackage{xetex-stack-renderer}',
) -> subprocess.CompletedProcess[str]:
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
