'''External renderer interface and command-line bridge.'''

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from . import build_default_registry
from .cache import RenderCache


class Backend(Protocol):
    '''Minimal contract implemented by every script renderer backend.'''

    name: str
    version: str

    def render(self, text: str, options: Mapping[str, object]) -> str:
        '''Render one complete script run to a TeX snippet.'''
        ...


@dataclass(frozen=True)
class RenderRequest:
    digest: str
    script: str
    backend_version: str
    options: dict[str, object]
    text: str


def canonical_options(options: Mapping[str, object] | None = None) -> str:
    return json.dumps(
        dict(options or {}),
        ensure_ascii=True,
        sort_keys=True,
        separators=(',', ':'),
    )


def request_signature(
    script: str,
    backend_version: str,
    text: str,
    options: Mapping[str, object] | None = None,
) -> str:
    codepoints = ','.join(f'{ord(character):X}' for character in text)
    return (
        f'XSR2|script={script}|backend_version={backend_version}'
        f'|options={canonical_options(options)}|codepoints={codepoints}'
    )


def request_digest(
    script: str,
    backend_version: str,
    text: str,
    options: Mapping[str, object] | None = None,
) -> str:
    signature = request_signature(script, backend_version, text, options)
    return hashlib.md5(signature.encode('ascii'), usedforsecurity=False).hexdigest().upper()


def response_filename(
    jobname: str,
    script: str,
    backend_version: str,
    text: str,
    options: Mapping[str, object] | None = None,
) -> str:
    digest = request_digest(script, backend_version, text, options)
    return f'{jobname}.xsr-{digest}.tex'


class Renderer:
    def __init__(self, cache: RenderCache | None = None) -> None:
        self.cache = cache
        self._backends: dict[str, Backend] = {}

    def register(self, backend: Backend) -> None:
        if backend.name in self._backends:
            raise ValueError(f'backend already registered: {backend.name}')
        self._backends[backend.name] = backend

    def backend_version(self, script: str) -> str:
        try:
            return self._backends[script].version
        except KeyError as error:
            raise ValueError(f'unknown backend: {script}') from error

    def render(
        self,
        script: str,
        text: str,
        options: Mapping[str, object] | None = None,
    ) -> str:
        try:
            backend = self._backends[script]
        except KeyError as error:
            raise ValueError(f'unknown backend: {script}') from error

        normalized_options = dict(options or {})
        key = RenderCache.key(backend.name, backend.version, text, normalized_options)
        if self.cache is not None:
            cached = self.cache.get(key)
            if cached is not None:
                return cached

        tex = backend.render(text, normalized_options)
        if self.cache is not None:
            self.cache.put(key, tex)
        return tex


def default_renderer(cache_dir: str | Path | None = None) -> Renderer:
    from .egyptian import EgyptianBackend

    renderer = Renderer(RenderCache(cache_dir) if cache_dir is not None else None)
    renderer.register(EgyptianBackend())
    return renderer


def read_request(path: Path) -> RenderRequest:
    lines = path.read_text(encoding='utf-8').splitlines()
    if not lines or lines[0] != 'XSR2':
        raise ValueError(f'invalid XSR2 request: {path}')

    fields: dict[str, str] = {}
    for line in lines[1:]:
        key, separator, value = line.partition('=')
        if not separator or key in fields:
            raise ValueError(f'invalid XSR2 request field: {line!r}')
        fields[key] = value

    required = {'digest', 'script', 'backend_version', 'options', 'codepoints'}
    if fields.keys() != required:
        raise ValueError(f'invalid XSR2 request fields: {sorted(fields)}')

    try:
        options = json.loads(fields['options'])
    except json.JSONDecodeError as error:
        raise ValueError(f'invalid renderer options: {error}') from error
    if not isinstance(options, dict):
        raise ValueError('renderer options must be a JSON object')

    encoded = fields['codepoints']
    text = ''.join(chr(int(item, 16)) for item in encoded.split(',') if item)
    expected = request_digest(
        fields['script'], fields['backend_version'], text, options
    )
    actual_digest = fields['digest']
    if actual_digest != expected:
        raise ValueError(
            f'request digest mismatch: expected {expected}, got {actual_digest}'
        )

    return RenderRequest(
        digest=expected,
        script=fields['script'],
        backend_version=fields['backend_version'],
        options=options,
        text=text,
    )


def write_tex(path: Path, tex: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tex, encoding='utf-8', newline='\n')


def render_request(args: argparse.Namespace) -> int:
    request = read_request(args.input)
    if request.script != args.backend:
        raise ValueError(
            f'request is for {request.script!r}, but {args.backend!r} was requested'
        )
    expected_name = f'.xsr-{request.digest}.tex'
    if not args.output.name.endswith(expected_name):
        raise ValueError(f'response filename must end with {expected_name}')

    renderer = default_renderer(args.cache_dir)
    actual_version = renderer.backend_version(request.script)
    if request.backend_version != actual_version:
        raise ValueError(
            f'backend version mismatch: request has {request.backend_version!r}, '
            f'installed backend is {actual_version!r}'
        )
    write_tex(
        args.output,
        renderer.render(request.script, request.text, request.options),
    )
    return 0


def preprocess(args: argparse.Namespace) -> int:
    source = args.input.read_text(encoding='utf-8')
    registry = build_default_registry()
    output_dir: Path = args.output_dir
    jobname = args.jobname or args.input.stem
    cache_dir = args.cache_dir or output_dir / '.xsr-cache'
    renderer = default_renderer(cache_dir)
    options: dict[str, object] = {}
    manifest_runs: list[dict[str, object]] = []

    for number, run in enumerate(registry.script_runs(source), start=1):
        assert run.script is not None
        backend_version = renderer.backend_version(run.script)
        digest = request_digest(run.script, backend_version, run.text, options)
        response = output_dir / response_filename(
            jobname, run.script, backend_version, run.text, options
        )
        write_tex(response, renderer.render(run.script, run.text, options))
        manifest_runs.append(
            {
                'number': number,
                'digest': digest,
                'script': run.script,
                'backend_version': backend_version,
                'options': options,
                'start': run.start,
                'end': run.end,
                'codepoints': [f'{ord(character):X}' for character in run.text],
                'response': response.name,
            }
        )

    source_digest = hashlib.sha256(source.encode('utf-8')).hexdigest()
    manifest = {
        'format': 'XSR-PREPROCESS-2',
        'source': str(args.input),
        'source_sha256': source_digest,
        'runs': manifest_runs,
    }
    manifest_path = output_dir / f'{jobname}.xsr-manifest.json'
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
        newline='\n',
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='xsr-render')
    subparsers = parser.add_subparsers(dest='command', required=True)

    render_parser = subparsers.add_parser('render', help='render one TeX request')
    render_parser.add_argument('--backend', required=True)
    render_parser.add_argument('--input', type=Path, required=True)
    render_parser.add_argument('--output', type=Path, required=True)
    render_parser.add_argument('--cache-dir', type=Path, required=True)
    render_parser.set_defaults(func=render_request)

    preprocess_parser = subparsers.add_parser(
        'preprocess', help='prepare content-addressed responses before XeLaTeX'
    )
    preprocess_parser.add_argument('--input', type=Path, required=True)
    preprocess_parser.add_argument('--output-dir', type=Path, required=True)
    preprocess_parser.add_argument('--jobname')
    preprocess_parser.add_argument('--cache-dir', type=Path)
    preprocess_parser.set_defaults(func=preprocess)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as error:
        parser.exit(2, f'xsr-render: error: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
