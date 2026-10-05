import json
from pathlib import Path

import pytest

from xsr.cache import RenderCache
from xsr.font_metrics import decode_path
from xsr.egyptian import BACKEND_VERSION, EgyptianBackend
from xsr.renderer import (
    RenderRequest,
    Renderer,
    canonical_options,
    main,
    read_request,
    request_digest,
)


def ehfc_run() -> str:
    return chr(0x13000) + chr(0x13431) + chr(0x13050)


def write_request(path: Path, text: str, options: dict) -> str:
    digest = request_digest('egyptian', BACKEND_VERSION, text, options)
    codepoints = ','.join(f'{ord(character):X}' for character in text)
    path.write_text(
        '\n'.join(
            [
                'XSR2',
                f'digest={digest}',
                'script=egyptian',
                f'backend_version={BACKEND_VERSION}',
                f'options={canonical_options(options)}',
                f'codepoints={codepoints}',
                '',
            ]
        ),
        encoding='utf-8',
    )
    return digest


def test_backend_parses_and_renders_one_complete_run(tmp_path: Path, font_options) -> None:
    renderer = Renderer(RenderCache(tmp_path / 'cache'))
    renderer.register(EgyptianBackend())
    run = ehfc_run()

    tex = renderer.render('egyptian', run, font_options)

    assert tex.startswith(r'\xsrBackendLayoutResult{egyptian}{3}')
    assert f'{{{BACKEND_VERSION}}}{{xsr-native-0.7}}' in tex
    assert r'\xsrEgyptianLayout' in tex
    assert tex.count(r'\xsrEgyptianGlyph') == 2
    assert len(list((tmp_path / 'cache').glob('*.tex'))) == 1
    assert renderer.render('egyptian', run, font_options) == tex


def test_render_request_protocol_is_bound_to_all_inputs(tmp_path: Path, font_options) -> None:
    run = ehfc_run()
    request_path = tmp_path / 'run.req'
    digest = write_request(request_path, run, font_options)
    response = tmp_path / f'run.xsr-{digest}.tex'

    request = read_request(request_path)
    assert request == RenderRequest(
        digest=digest,
        script='egyptian',
        backend_version=BACKEND_VERSION,
        options=font_options,
        text=run,
    )
    assert main(
        [
            'render',
            '--backend',
            'egyptian',
            '--input',
            str(request_path),
            '--output',
            str(response),
            '--cache-dir',
            str(tmp_path / 'cache'),
        ]
    ) == 0
    assert response.read_text(encoding='utf-8').startswith(
        r'\xsrBackendLayoutResult{egyptian}{3}'
    )


def test_preprocess_writes_content_addressed_response_and_manifest(
    tmp_path: Path, font_options,
) -> None:
    source = tmp_path / 'sample.tex'
    source.write_text(f'ordinary {ehfc_run()} ordinary\n', encoding='utf-8')
    output = tmp_path / 'prepared'

    assert main(
        [
            'preprocess', '--font', decode_path(font_options['font_codepoints']),
            '--input',
            str(source),
            '--output-dir',
            str(output),
        ]
    ) == 0

    manifest = json.loads(
        (output / 'sample.xsr-manifest.json').read_text(encoding='utf-8')
    )
    run = manifest['runs'][0]
    assert manifest['format'] == 'XSR-PREPROCESS-2'
    assert run['script'] == 'egyptian'
    assert run['backend_version'] == BACKEND_VERSION
    assert run['options'] == font_options
    assert run['digest'] in run['response']
    assert (output / run['response']).is_file()


def test_changed_run_cannot_reuse_same_numbered_response(tmp_path: Path, font_options) -> None:
    source = tmp_path / 'sample.tex'
    output = tmp_path / 'prepared'

    source.write_text(f'ordinary {chr(0x13000)} ordinary\n', encoding='utf-8')
    assert main(
        ['preprocess', '--font', decode_path(font_options['font_codepoints']), '--input', str(source), '--output-dir', str(output)]
    ) == 0
    first_manifest = json.loads(
        (output / 'sample.xsr-manifest.json').read_text(encoding='utf-8')
    )
    first_response = first_manifest['runs'][0]['response']

    source.write_text(f'ordinary {chr(0x13001)} ordinary\n', encoding='utf-8')
    assert main(
        ['preprocess', '--font', decode_path(font_options['font_codepoints']), '--input', str(source), '--output-dir', str(output)]
    ) == 0
    second_manifest = json.loads(
        (output / 'sample.xsr-manifest.json').read_text(encoding='utf-8')
    )
    second_response = second_manifest['runs'][0]['response']

    assert first_response != second_response
    assert (output / first_response).is_file()
    assert (output / second_response).is_file()


def test_request_digest_rejects_changed_codepoints(tmp_path: Path, font_options) -> None:
    request_path = tmp_path / 'run.req'
    write_request(request_path, chr(0x13000), font_options)
    request_path.write_text(
        request_path.read_text(encoding='utf-8').replace('13000', '13001'),
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='request digest mismatch'):
        read_request(request_path)
