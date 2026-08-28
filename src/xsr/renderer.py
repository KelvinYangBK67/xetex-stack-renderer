"""External renderer interface and command-line bridge."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from . import build_default_registry
from .cache import RenderCache


class Backend(Protocol):
    """Minimal contract implemented by every script renderer backend."""

    name: str
    version: str

    def render(self, text: str, options: Mapping[str, object]) -> str:
        """Render one complete script run to a TeX snippet."""
        ...


class Renderer:
    def __init__(self, cache: RenderCache | None = None) -> None:
        self.cache = cache
        self._backends: dict[str, Backend] = {}

    def register(self, backend: Backend) -> None:
        if backend.name in self._backends:
            raise ValueError(f"backend already registered: {backend.name}")
        self._backends[backend.name] = backend

    def render(
        self,
        script: str,
        text: str,
        options: Mapping[str, object] | None = None,
    ) -> str:
        try:
            backend = self._backends[script]
        except KeyError as error:
            raise ValueError(f"unknown backend: {script}") from error

        normalized_options = dict(options or {})
        key = RenderCache.key(
            backend.name, backend.version, text, normalized_options
        )
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


def read_request(path: Path) -> tuple[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 3 or lines[0] != "XSR1":
        raise ValueError(f"invalid XSR request: {path}")
    if not lines[1].startswith("script=") or not lines[2].startswith("codepoints="):
        raise ValueError(f"invalid XSR request fields: {path}")
    script = lines[1].removeprefix("script=")
    encoded = lines[2].removeprefix("codepoints=").strip()
    text = "".join(chr(int(item, 16)) for item in encoded.split())
    return script, text


def write_tex(path: Path, tex: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tex, encoding="utf-8", newline="\n")


def render_request(args: argparse.Namespace) -> int:
    script, text = read_request(args.input)
    if script != args.backend:
        raise ValueError(
            f"request is for {script!r}, but {args.backend!r} was requested"
        )
    renderer = default_renderer(args.cache_dir)
    write_tex(args.output, renderer.render(script, text))
    return 0


def preprocess(args: argparse.Namespace) -> int:
    source = args.input.read_text(encoding="utf-8")
    registry = build_default_registry()
    output_dir: Path = args.output_dir
    jobname = args.jobname or args.input.stem
    cache_dir = args.cache_dir or output_dir / ".xsr-cache"
    renderer = default_renderer(cache_dir)
    manifest_runs: list[dict[str, object]] = []

    for number, run in enumerate(registry.script_runs(source), start=1):
        assert run.script is not None
        response = output_dir / f"{jobname}.xsr-{number}.tex"
        write_tex(response, renderer.render(run.script, run.text))
        manifest_runs.append(
            {
                "number": number,
                "script": run.script,
                "start": run.start,
                "end": run.end,
                "codepoints": [f"{ord(char):X}" for char in run.text],
                "response": response.name,
            }
        )

    source_digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    manifest = {
        "format": "XSR-PREPROCESS-1",
        "source": str(args.input),
        "source_sha256": source_digest,
        "runs": manifest_runs,
    }
    manifest_path = output_dir / f"{jobname}.xsr-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xsr-render")
    subparsers = parser.add_subparsers(dest="command", required=True)

    render_parser = subparsers.add_parser("render", help="render one TeX request")
    render_parser.add_argument("--backend", required=True)
    render_parser.add_argument("--input", type=Path, required=True)
    render_parser.add_argument("--output", type=Path, required=True)
    render_parser.add_argument("--cache-dir", type=Path, required=True)
    render_parser.set_defaults(func=render_request)

    preprocess_parser = subparsers.add_parser(
        "preprocess", help="prepare responses before running XeLaTeX"
    )
    preprocess_parser.add_argument("--input", type=Path, required=True)
    preprocess_parser.add_argument("--output-dir", type=Path, required=True)
    preprocess_parser.add_argument("--jobname")
    preprocess_parser.add_argument("--cache-dir", type=Path)
    preprocess_parser.set_defaults(func=preprocess)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

