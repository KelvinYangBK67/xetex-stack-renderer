"""Conservative recursive TeX source discovery, not macro expansion.

Every distinct run is prepared for every discovered/explicit font. This makes
scoped switches deterministic without pretending to interpret TeX execution.
"""
from pathlib import Path
import hashlib
import json
import re

from . import build_default_registry
from .errors import XSRError
from .font_metrics import font_options, tex_font_path

COMMENT = re.compile(r'(?<!\\)%[^\n]*')
INCLUDE = re.compile(r'\\(?:input|include)\s*\{([^{}]+)\}')
FONT = re.compile(r'\\xsr([A-Za-z]+?)(?:DefaultFont|Font)\s*\{([^{}]+)\}')


def discover_sources(inputs):
    found, active = {}, set()
    roots = [Path(p).resolve().parent for p in inputs]

    def visit(path):
        path = path.resolve()
        if path in active:
            raise XSRError('XSR-PREPROCESS', f'cyclic input/include at {path}')
        if path in found:
            return
        try:
            raw = path.read_text(encoding='utf-8-sig')
        except OSError as error:
            raise XSRError('XSR-SOURCE-MISSING', f'cannot read source {path}: {error.strerror}') from error
        source = COMMENT.sub('', raw)
        found[path] = (raw, source)
        active.add(path)
        for target in INCLUDE.findall(source):
            if '\\' in target or '#' in target:
                raise XSRError('XSR-PREPROCESS', f'input/include must be a literal filename: {target}')
            child = Path(target)
            if not child.suffix:
                child = child.with_suffix('.tex')
            candidates = [root / child for root in roots] + [path.parent / child]
            resolved = next((p for p in candidates if p.is_file()), candidates[0])
            visit(resolved)
        active.remove(path)

    for path in inputs:
        visit(Path(path))
    return found


def preprocess(args):
    from .renderer import default_renderer, request_digest, response_filename, write_tex
    from .source import source_runs

    inputs = args.input if isinstance(args.input, list) else [args.input]
    sources = discover_sources(inputs)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    workdir = (args.tex_workdir or output_dir).resolve()
    jobname = args.jobname or inputs[0].stem
    renderer = default_renderer(args.cache_dir or output_dir / '.xsr-cache')
    registry = build_default_registry()
    selections = {spec.name: {} for spec in registry.scripts}
    explicit = args.font or []
    if isinstance(explicit, Path):
        explicit = [explicit]
    for path in explicit:
        resolved = Path(tex_font_path(path))
        for script in selections:
            selections[script][resolved.as_posix()] = resolved
    for _, source in sources.values():
        for label, spelling in FONT.findall(source):
            script = label.lower()
            if script not in selections:
                continue
            if '\\' in spelling:
                raise XSRError('XSR-PREPROCESS',
                               'use literal forward-slash font paths in discovered commands')
            resolved = Path(spelling)
            if not resolved.is_absolute():
                resolved = workdir / resolved
            selections[script][spelling] = resolved.resolve()

    source_texts = [source for _, source in sources.values()]
    profiles = {}
    for script, fonts in selections.items():
        profiles[script] = []
        extras = renderer.preprocess_extras(script, source_texts)
        for spelling, resolved in sorted(fonts.items()):
            options = font_options(resolved, spelling=spelling)
            render_options = font_options(resolved)
            profiles[script].extend((options | extra, render_options | extra)
                                    for extra in extras)
    runs, emitted = [], set()
    for path, (raw, source) in sources.items():
        for run in source_runs(source, registry):
            if not profiles[run.script]:
                raise XSRError('XSR-FONT-NOT-SELECTED',
                               f'select a {run.script} font in the source or supply --font')
            version = renderer.backend_version(run.script)
            for options, render_options in profiles[run.script]:
                digest = request_digest(run.script, version, run.text, options)
                filename = response_filename(jobname, run.script, version, run.text, options)
                if digest not in emitted:
                    write_tex(output_dir / filename,
                              renderer.render(run.script, run.text, render_options))
                    emitted.add(digest)
                runs.append(dict(number=len(runs)+1, digest=digest, script=run.script,
                                 backend_version=version, options=options, source=str(path),
                                 start=run.start, end=run.end,
                                 codepoints=[f'{ord(ch):X}' for ch in run.text],
                                 response=filename))
    manifest = dict(format='XSR-PREPROCESS-2', source=str(inputs[0]),
                    source_sha256=hashlib.sha256(sources[inputs[0].resolve()][0].encode('utf-8')).hexdigest(),
                    sources=[dict(path=str(p), sha256=hashlib.sha256(raw.encode('utf-8')).hexdigest())
                             for p, (raw, _) in sources.items()], runs=runs)
    (output_dir / f'{jobname}.xsr-manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return 0
