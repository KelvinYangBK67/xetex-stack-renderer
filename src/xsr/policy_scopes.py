"""Missing-policy scopes for literal font runs, including input/include order."""
from pathlib import Path
import re
from .errors import XSRError

TOKEN = re.compile(r'\\xsrMissingGlyphPolicy\s*\{([^{}]*)\}|\\(?:input|include)\s*\{([^{}]+)\}|[{}]')


def policy_spans(sources):
    result = {path: [] for path in sources}
    visited, stack, state = set(), [], 'box'
    roots = [path.parent for path in sources]

    def visit(path):
        nonlocal state
        visited.add(path)
        source = sources[path][1]
        cursor = 0
        for token in TOKEN.finditer(source):
            result[path].append((cursor, token.end(), state))
            cursor = token.end()
            if token[1] is not None:
                if token[1] not in ('box', 'error'):
                    raise XSRError('XSR-MISSING-POLICY', 'use box or error')
                state = token[1]
            elif token[2] is not None:
                child = Path(token[2])
                if not child.suffix:
                    child = child.with_suffix('.tex')
                target = next(((root/child).resolve() for root in roots if (root/child).resolve() in sources), None)
                if target is not None:
                    visit(target)
            elif token.group() == '{':
                stack.append(state)
            elif stack:
                state = stack.pop()
        result[path].append((cursor, len(source)+1, state))

    for path in sources:
        if path not in visited:
            visit(path)
    return result
