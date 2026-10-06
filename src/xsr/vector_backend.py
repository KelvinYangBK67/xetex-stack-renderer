"""Direct SVG and optional provider backends over the existing XSR bridge."""
import hashlib
from pathlib import Path
from .errors import XSRError
from .font_metrics import encode_path, decode_path
from .providers import ExternalProvider, ProviderConfig
from .synthetic import policy, warn
from .vector import IMPORT_VERSION, import_svg, tofu, glyph_tex


def file_digest(path):
    return hashlib.md5(Path(path).read_bytes(), usedforsecurity=False).hexdigest().upper()


def input_options(path, *, spelling=None, provider=False):
    prefix = 'provider' if provider else 'source'
    return {prefix + '_codepoints': encode_path(spelling if spelling is not None else Path(path).resolve().as_posix()),
            prefix + '_digest': file_digest(path)}


class VectorBackend:
    version = IMPORT_VERSION

    def __init__(self, name='vector', cache_dir='.xsr-cache'):
        self.name = name
        self.cache_dir = cache_dir
        self._glyphs = {}

    def prepare_request(self, text, options):
        options = dict(options)
        missing_policy = policy(options)
        prefix = 'source' if self.name == 'vector' else 'provider'
        spelling = options.get(prefix + '_codepoints', '')
        path = Path(decode_path(spelling)).resolve() if spelling else None
        if path:
            try:
                digest = file_digest(path)
            except OSError as error:
                raise XSRError('XSR-SVG-MISSING' if prefix == 'source' else 'XSR-PROVIDER-CONFIG', str(error)) from error
            if options.get(prefix + '_digest', digest) != digest:
                raise XSRError('XSR-STALE', 'external input changed; regenerate response')
            options[prefix + '_codepoints'] = encode_path(path.as_posix())
            options[prefix + '_digest'] = digest
        diagnostic = None
        if self.name == 'vector':
            if path is None:
                raise XSRError('XSR-SVG-MISSING', 'select a source SVG')
            data = path.read_bytes()
            actual_digest = hashlib.md5(data, usedforsecurity=False).hexdigest().upper()
            if actual_digest != options['source_digest']:
                raise XSRError('XSR-STALE', 'SVG changed while reading; retry')
            glyph = import_svg(data)
        else:
            style = options.get('style', 'serif')
            if not isinstance(style, str) or not style or '\x00' in style or '\x00' in text:
                raise XSRError('XSR-PROVIDER-CONFIG', 'invalid literal glyph/style')
            try:
                if path is None:
                    raise XSRError('XSR-PROVIDER-UNAVAILABLE', 'no provider configuration selected')
                config = ProviderConfig.read(path)
                options['provider_identity'] = config.identity()
                data = ExternalProvider(config, self.cache_dir).obtain(text, style)
                glyph = import_svg(data)
            except XSRError as error:
                if missing_policy == 'error' or error.code not in {
                    'XSR-PROVIDER-UNAVAILABLE', 'XSR-PROVIDER-MISSING',
                    'XSR-PROVIDER-FAILED', 'XSR-PROVIDER-SVG'}:
                    raise
                diagnostic = error.code
                warn(error.code, str(error))
                glyph = tofu()
                data = diagnostic.encode('ascii')
        key = hashlib.sha256(data).hexdigest()
        options['svg_sha256'] = key
        options['importer_version'] = IMPORT_VERSION
        if diagnostic:
            options['diagnostic'] = diagnostic
        self._glyphs[key] = glyph
        return options

    def render(self, text, options):
        if 'svg_sha256' not in options:
            options = self.prepare_request(text, options)
        glyph = self._glyphs[options['svg_sha256']]
        warning = (r'\xsrVectorWarning{' + options['diagnostic'] + '}' if options.get('diagnostic') else '')
        return (r'\xsrBackendLayoutResult{' + self.name + '}{1}{' + options['svg_sha256'][:12]
                + '}{' + self.version + '}{restricted-svg}{' + warning + glyph_tex(glyph) + '}%\n')
