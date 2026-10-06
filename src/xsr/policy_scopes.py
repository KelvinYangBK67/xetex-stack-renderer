"""Missing-policy scopes for literal font runs, including input/include order."""
from pathlib import Path
import re
from .errors import XSRError
from .source_traversal import entrypoints, resolve_include

TOKEN = re.compile(r'\\xsrMissingGlyphPolicy\s*\{([^{}]*)\}|\\(?:input|include)\s*\{([^{}]+)\}|[{}]')


def policy_spans(sources):
    result = {path: [] for path in sources}
    active, stack, state = set(), [], 'box'

    def visit(path):
        nonlocal state
        if path in active:
            raise XSRError('XSR-PREPROCESS', f'cyclic input/include at {path}')
        active.add(path)
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
                visit(resolve_include(sources, path, token[2]))
            elif token.group() == '{':
                stack.append(state)
            elif stack:
                state = stack.pop()
        result[path].append((cursor, len(source)+1, state))

        active.remove(path)

    for path in entrypoints(sources):
        visit(path)
    return result
