"""Shell bridge files follow XeTeX's -output-directory, not shell cwd."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from xsr.renderer import canonical_options, default_renderer, main, request_digest, shell_bridge_path

ROOT = Path(__file__).resolve().parents[1]
A = chr(0x13000)
H = chr(0x13431)
B = chr(0x13050)


def request_file(path: Path, font_options: dict[str, object]) -> None:
    renderer = default_renderer()
    version = renderer.backend_version('egyptian')
    digest = request_digest('egyptian', version, A + H + B, font_options)
    path.write_text(
        '\n'.join([
            'XSR2', f'digest={digest}', 'script=egyptian',
            f'backend_version={version}',
            f'options={canonical_options(font_options)}',
            f'codepoints={ord(A):X},{ord(H):X},{ord(B):X}', '',
        ]),
        encoding='utf-8',
    )


@pytest.mark.parametrize('output_name', ['build', 'build with spaces', '測試-output'])
def test_relative_shell_request_and_cleanup_use_tex_output_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, font_options: dict[str, object],
    output_name: str,
) -> None:
    output = tmp_path / output_name
    output.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('TEXMF_OUTPUT_DIRECTORY', output_name)
    request = output / 'unit.xsr-request.req'
    response = output / 'unit.xsr-response.tex'
    request_file(request, font_options)

    assert main([
        'render', '--backend', 'egyptian',
        '--input', request.name, '--output', response.name,
        '--consume-request',
    ]) == 0
    assert r'\xsrBackendLayoutResult' in response.read_text(encoding='utf-8')
    assert not request.exists()
    assert not (tmp_path / response.name).exists()
    assert main(['cleanup', '--jobname', 'unit']) == 0
    assert not response.exists()


def test_absolute_bridge_paths_are_not_rebased(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, font_options: dict[str, object],
) -> None:
    output = tmp_path / 'build'
    output.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('TEXMF_OUTPUT_DIRECTORY', str(output))
    request = tmp_path / 'absolute.xsr-request.req'
    response = tmp_path / 'absolute.xsr-response.tex'
    request_file(request, font_options)
    assert shell_bridge_path(request) == request
    assert main([
        'render', '--backend', 'egyptian',
        '--input', str(request), '--output', str(response), '--consume-request',
    ]) == 0
    assert response.is_file()
    assert not (output / response.name).exists()


def test_shell_render_error_response_uses_output_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    build = tmp_path / 'build'
    build.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('TEXMF_OUTPUT_DIRECTORY', 'build')
    with pytest.raises(SystemExit) as error:
        main(['render', '--backend', 'egyptian',
              '--input', 'bad.xsr-request.req',
              '--output', 'bad.xsr-response.tex', '--consume-request'])
    assert error.value.code == 2
    assert r'\xsrRendererError{XSR-IO}' in (
        build / 'bad.xsr-response.tex').read_text(encoding='utf-8')


@pytest.mark.skipif(shutil.which('xelatex') is None, reason='xelatex unavailable')
@pytest.mark.parametrize('directory_kind', ['relative', 'absolute'])
def test_xelatex_shell_escape_with_separate_output_directory(
    tmp_path: Path, directory_kind: str,
) -> None:
    # TeX Live 2024+ exports -output-directory to child processes.
    from conftest import NEW_GARDINER

    build = tmp_path / 'build'
    build.mkdir()
    source = tmp_path / 'bridge.tex'
    source.write_text(
        '\\documentclass{article}\n'
        '\\usepackage[mode=shell]{xetex-stack-renderer}\n'
        f'\\xsrEgyptianDefaultFont{{{NEW_GARDINER.as_posix()}}}\n'
        '\\begin{document}\n'
        f'{A}{H}{B} and {A}\n'
        '\\end{document}\n',
        encoding='utf-8',
    )
    output_dir = 'build' if directory_kind == 'relative' else str(build)
    env = os.environ.copy()
    env.pop('TEXMF_OUTPUT_DIRECTORY', None)
    env['TEXINPUTS'] = str(ROOT / 'tex') + os.pathsep + env.get('TEXINPUTS', '')
    env['PYTHONPATH'] = str(ROOT / 'src') + os.pathsep + env.get('PYTHONPATH', '')
    result = subprocess.run(
        ['xelatex', '-shell-escape', '-interaction=nonstopmode',
         '-halt-on-error', f'-output-directory={output_dir}', source.name],
        cwd=tmp_path, env=env, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=90,
    )
    assert result.returncode == 0, result.stdout
    assert result.stdout.count('XSR-LAYOUT script=egyptian') == 2
    assert (build / 'bridge.pdf').is_file()
    assert not list(tmp_path.glob('bridge.xsr-*'))
    assert not list(build.glob('bridge.xsr-*'))
