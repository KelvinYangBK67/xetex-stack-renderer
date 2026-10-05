"""Discover literal script runs in TeX source without macro expansion."""
import re
from .registry import DetectedRun
from .errors import XSRError

TEXT = re.compile(r'\\xsr([A-Za-z]+)Text\s*\{')


def source_runs(source, registry):
    names = {spec.name for spec in registry.scripts}
    spans = []
    for match in TEXT.finditer(source):
        script = match.group(1).lower()
        if script not in names:
            continue
        start = match.end()
        depth = 1
        end = start
        while end < len(source) and depth:
            if source[end] == '{':
                depth += 1
            elif source[end] == '}':
                depth -= 1
            end += 1
        if depth:
            raise XSRError('XSR-PREPROCESS', f'unclosed literal {match.group(0)} argument')
        spans.append((start, end - 1, script))
    runs = [run for run in registry.script_runs(source)
            if not any(a <= run.start < b for a, b, _ in spans)]
    runs.extend(DetectedRun(script, source[a:b], a, b)
                for a, b, script in spans)
    return sorted(runs, key=lambda run: run.start)