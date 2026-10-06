"""Literal, brace-scoped vector request discovery (no TeX macro expansion)."""
import re
from pathlib import Path
from .errors import XSRError
from .source_traversal import entrypoints, resolve_include
from .inline import GlyphRegistry
import math
from .vector_backend import input_options
from .renderer import request_digest

COMMAND = re.compile(r'\\xsr(VectorGlyph|ProviderGlyph|KageGlyph|VectorProvider|KageProvider|VectorStyle|KageStyle|MissingGlyphPolicy)\s*\{([^{}]*)\}')
INCLUDE = re.compile(r'\\(?:input|include)\s*\{([^{}]+)\}')
REGISTER = re.compile(r'\\GlyphRegister\s*\{([^{}]*)\}\s*\{([^{}]*)\}')
USE = re.compile(r'\\Glyph\s*(?:\[([^]]*)\])?\s*\{([^{}]*)\}')
INLINE_COMMAND = re.compile(REGISTER.pattern + '|' + USE.pattern)
TOKEN = re.compile(COMMAND.pattern + '|' + INLINE_COMMAND.pattern + '|' + INCLUDE.pattern + r'|[{}]')


def prepare_vectors(sources, workdir, bundle, renderer, responses):
    runs = []
    registry = GlyphRegistry(workdir)
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
            registration = REGISTER.fullmatch(value)
            use = USE.fullmatch(value)
            if registration:
                label, file = registration.groups()
                if any(c in label+file for c in '\\{}%#\x00\r\n'):
                    raise XSRError('XSR-PREPROCESS', 'glyph registration requires literal arguments')
                registry.register(label, file)
                continue
            if use:
                adjustment, label = use.groups()
                for option in (adjustment or '').split(','):
                    if not option.strip():
                        continue
                    key, separator, setting = option.partition('=')
                    if key.strip() not in ('scale','raise') or not separator or not setting.strip():
                        raise XSRError('XSR-INLINE-OPTION', 'only scale and raise are supported')
                    if key.strip() == 'scale':
                        try:
                            if not re.fullmatch(r'[+]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?', setting.strip()):
                                raise ValueError()
                            factor = float(setting)
                            if not math.isfinite(factor) or factor <= 0:
                                raise ValueError()
                        except ValueError as error:
                            raise XSRError('XSR-INLINE-GEOMETRY', 'scale must be finite and positive') from error
                command, value = 'AssetGlyph', registry.file(label)
            else:
                command, value = COMMAND.fullmatch(value).groups()
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
            if command in ('VectorGlyph','AssetGlyph'):
                resolved = (workdir/value).resolve()
                options = input_options(resolved, spelling=value)
                actual = input_options(resolved)
                script, text = ('asset' if command == 'AssetGlyph' else 'vector'), ''
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
            if digest not in responses:
                responses[digest] = renderer.render(script, text, actual)
            runs.append(dict(digest=digest, script=script, backend_version=version,
                             options=options, source=str(path), start=token.start(), end=token.end(),
                             codepoints=[f'{ord(c):X}' for c in text], response=bundle))

        active.remove(path)

    for path in entrypoints(sources):
        visit(path)
    return runs
