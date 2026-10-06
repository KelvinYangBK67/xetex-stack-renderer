"""Literal, brace-scoped vector request discovery (no TeX macro expansion)."""
import re
from pathlib import Path
from .errors import XSRError
from .source_traversal import entrypoints, resolve_include
from .vector_backend import input_options
from .renderer import request_digest, response_filename, write_tex

COMMAND = re.compile(r'\\xsr(VectorGlyph|ProviderGlyph|KageGlyph|VectorProvider|KageProvider|VectorStyle|KageStyle|MissingGlyphPolicy)\s*\{([^{}]*)\}')
INCLUDE = re.compile(r'\\(?:input|include)\s*\{([^{}]+)\}')
TOKEN = re.compile(COMMAND.pattern + '|' + INCLUDE.pattern + r'|[{}]')


def prepare_vectors(sources, workdir, output_dir, jobname, renderer):
    runs, emitted = [], set()
    state = {'provider': '', 'style': 'serif', 'missing_glyph_policy': 'box'}
    stack, active = [], set()

    def visit(path):
        nonlocal state
        if path in active:
            raise XSRError('XSR-PREPROCESS', f'cyclic input/include at {path}')
        active.add(path)
        source = sources[path][1]
        for token in TOKEN.finditer(source):
            value = token.group()
            if value == '{':
                stack.append(dict(state))
                continue
            if value == '}':
                if stack:
                    state = stack.pop()
                continue
            include = INCLUDE.fullmatch(value)
            if include:
                visit(resolve_include(sources, path, include[1]))
                continue
            match = COMMAND.fullmatch(value)
            command, value = match.groups()
            if any(c in value for c in '\\{}%#\x00\r\n'):
                raise XSRError('XSR-PREPROCESS', 'external glyph commands require literal arguments')
            if command.endswith('Provider'):
                state['provider'] = value
                continue
            if command.endswith('Style'):
                if not re.fullmatch('[A-Za-z0-9_-]+', value) or (command == 'KageStyle' and value not in ('serif','sans')):
                    raise XSRError('XSR-PREPROCESS', 'invalid literal provider style')
                state['style'] = value
                continue
            if command == 'MissingGlyphPolicy':
                if value not in ('box','error'):
                    raise XSRError('XSR-MISSING-POLICY', 'use box or error')
                state['missing_glyph_policy'] = value
                continue
            if command == 'VectorGlyph':
                resolved = (workdir/value).resolve()
                options = input_options(resolved, spelling=value)
                actual = input_options(resolved)
                script, text = 'vector', ''
            else:
                script, text = 'provider', value
                common = {k: state[k] for k in ('style','missing_glyph_policy')}
                spelling = state['provider']
                if spelling:
                    resolved = (workdir/spelling).resolve()
                    options = input_options(resolved, spelling=spelling, provider=True)
                    actual = input_options(resolved, provider=True)
                else:
                    options = actual = {'provider_codepoints': '', 'provider_digest': ''}
                options, actual = options | common, actual | common
            version = renderer.backend_version(script)
            digest = request_digest(script, version, text, options)
            filename = response_filename(jobname, script, version, text, options)
            if digest not in emitted:
                write_tex(output_dir/filename, renderer.render(script, text, actual))
                emitted.add(digest)
            runs.append(dict(digest=digest, script=script, backend_version=version,
                             options=options, source=str(path), start=token.start(), end=token.end(),
                             codepoints=[f'{ord(c):X}' for c in text], response=filename))

        active.remove(path)

    for path in entrypoints(sources):
        visit(path)
    return runs
