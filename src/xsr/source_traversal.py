"""Shared literal include resolution; execution is occurrence-based, not visited-based."""
from pathlib import Path
from .errors import XSRError


class SourceMap(dict):
    def __init__(self, inputs):
        super().__init__()
        self.inputs = tuple(Path(path).resolve() for path in inputs)


def entrypoints(sources):
    return getattr(sources, 'inputs', tuple(sources)[:1])


def resolve_include(sources, parent, spelling):
    if '\\' in spelling or '#' in spelling:
        raise XSRError('XSR-PREPROCESS', f'input/include must be a literal filename: {spelling}')
    child = Path(spelling)
    if not child.suffix:
        child = child.with_suffix('.tex')
    # Parent-first, then explicit input roots, with exactly the same rule in
    # discovery and execution. Never search incidental previously visited dirs.
    candidates = [(parent.parent/child).resolve()]
    candidates += [(root.parent/child).resolve() for root in entrypoints(sources)]
    return next((path for path in candidates if path.is_file()), candidates[0])
