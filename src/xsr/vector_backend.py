"""Shared file-asset, direct SVG and optional provider backends over the existing XSR bridge."""
import hashlib
from pathlib import Path
from .errors import XSRError
from .font_metrics import encode_path, decode_path
from .providers import ExternalProvider, ProviderConfig
from .synthetic import policy, warn
from .vector import IMPORT_VERSION, import_svg, tofu
from .inline import INLINE_VERSION, resolve_asset, vector_asset, inline_tex


def file_digest(path):
    return hashlib.md5(Path(path).read_bytes(), usedforsecurity=False).hexdigest().upper()


def input_options(path, *, spelling=None, provider=False):
    prefix = 'provider' if provider else 'source'
    return {prefix + '_codepoints': encode_path(spelling if spelling is not None else Path(path).resolve().as_posix()),
            prefix + '_digest': file_digest(path)}


class VectorBackend:
    version = INLINE_VERSION

    def __init__(self, name='vector', cache_dir=None):
        self.name = name
        self.cache_dir = cache_dir
        self._glyphs = {}
        self._providers = {}

    def prepare_request(self, text, options):
        options = dict(options)
        missing_policy = policy(options)
        prefix = 'source' if self.name != 'provider' else 'provider'
        spelling = options.get(prefix + '_codepoints', '')
        path = Path(decode_path(spelling)).resolve() if spelling else None
        if path:
            try:
                digest = file_digest(path)
            except OSError as error:
                code = 'XSR-PROVIDER-CONFIG' if prefix == 'provider' else ('XSR-ASSET-MISSING' if self.name == 'asset' else 'XSR-SVG-MISSING')
                raise XSRError(code, str(error)) from error
            if options.get(prefix + '_digest', digest) != digest:
                raise XSRError('XSR-STALE', 'external input changed; regenerate response')
            options[prefix + '_codepoints'] = encode_path(path.as_posix())
            options[prefix + '_digest'] = digest
        diagnostic = None
        if self.name != 'provider':
            if path is None:
                raise XSRError('XSR-ASSET-MISSING' if self.name == 'asset' else 'XSR-SVG-MISSING', 'select a source asset')
            data = path.read_bytes()
            actual_digest = hashlib.md5(data, usedforsecurity=False).hexdigest().upper()
            if actual_digest != options['source_digest']:
                raise XSRError('XSR-STALE', 'asset changed while reading; retry')
            if self.name == 'vector' and path.suffix.lower() != '.svg':
                raise XSRError('XSR-SVG-INVALID', 'direct SVG API requires an SVG file')
            asset = resolve_asset(path)
            if asset.identity[1] != hashlib.sha256(data).hexdigest():
                raise XSRError('XSR-STALE', 'asset changed while resolving; retry')
        else:
            style = options.get('style', 'serif')
            if not isinstance(style, str) or not style or '\x00' in style or '\x00' in text:
                raise XSRError('XSR-PROVIDER-CONFIG', 'invalid literal glyph/style')
            try:
                if path is None:
                    raise XSRError('XSR-PROVIDER-UNAVAILABLE', 'no provider configuration selected')
                config = ProviderConfig.read(path)
                options['provider_identity'] = config.identity()
                from .renderer import canonical_options
                provider_key = canonical_options(config.identity())
                if provider_key not in self._providers:
                    self._providers[provider_key] = ExternalProvider(config, self.cache_dir)
                data = self._providers[provider_key].obtain(text, style)
                asset = vector_asset(import_svg(data), (str(path), hashlib.sha256(data).hexdigest()))
            except XSRError as error:
                if missing_policy == 'error' or error.code not in {
                    'XSR-PROVIDER-UNAVAILABLE', 'XSR-PROVIDER-MISSING',
                    'XSR-PROVIDER-FAILED', 'XSR-PROVIDER-SVG'}:
                    raise
                diagnostic = error.code
                warn(error.code, str(error))
                asset = vector_asset(tofu(), ('synthetic', diagnostic))
                data = diagnostic.encode('ascii')
        key = hashlib.sha256(data).hexdigest()
        options['svg_sha256'] = key
        options['importer_version'] = IMPORT_VERSION
        if diagnostic:
            options['diagnostic'] = diagnostic
        self._glyphs[key] = asset
        return options

    def render(self, text, options):
        if 'svg_sha256' not in options:
            options = self.prepare_request(text, options)
        glyph = self._glyphs[options['svg_sha256']]
        warning = (r'\xsrVectorWarning{' + options['diagnostic'] + '}' if options.get('diagnostic') else '')
        return (r'\xsrBackendLayoutResult{' + self.name + '}{1}{' + options['svg_sha256'][:12]
                + '}{' + self.version + '}{inline-assets}{' + warning + inline_tex(glyph) + '}%\n')
