"""Optional external SVG producers. No rendering engine is imported here."""
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
from .cache import RenderCache
from .errors import XSRError
from .vector import IMPORT_VERSION, import_svg


@dataclass(frozen=True)
class ProviderConfig:
    executable: str
    prefix_args: tuple[str, ...] = ()
    options: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    timeout: float = 30

    @classmethod
    def read(cls, path):
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8-sig'))
            if not isinstance(data, dict) or set(data) - {'executable', 'prefix_args', 'options', 'metadata', 'timeout'}:
                raise ValueError('unknown configuration field')
            config = cls(**data)
            if not isinstance(config.executable, str) or not config.executable or '\x00' in config.executable:
                raise ValueError('executable must be a nonempty literal string')
            if Path(config.executable).suffix.lower() in ('.bat', '.cmd'):
                raise ValueError('use an executable or explicit interpreter, not a shell wrapper')
            if not isinstance(config.prefix_args, (list, tuple)) or any(not isinstance(v, str) or '\x00' in v for v in config.prefix_args):
                raise ValueError('prefix_args must be an array of strings')
            if not isinstance(config.options, dict) or not isinstance(config.metadata, dict):
                raise ValueError('options and metadata must be objects')
            if not isinstance(config.timeout, (int, float)) or not 0 < config.timeout <= 300:
                raise ValueError('timeout must be in (0, 300] seconds')
            # Relative executable paths are anchored to the configuration file.
            executable = Path(config.executable)
            if not executable.is_absolute() and ('/' in config.executable or '\\' in config.executable):
                data['executable'] = str((Path(path).resolve().parent / executable).resolve())
            return cls(**data)
        except (OSError, ValueError, TypeError) as error:
            raise XSRError('XSR-PROVIDER-CONFIG', f'invalid provider config: {error}') from error

    def identity(self):
        return dict(executable=self.executable, prefix_args=list(self.prefix_args),
                    options=self.options, metadata=self.metadata, timeout=self.timeout)


class ExternalProvider:
    """Single-request implementation; obtain_many is an overridable batch seam."""
    def __init__(self, config, cache_dir):
        self.config = config
        self.cache_dir = Path(cache_dir)

    def obtain_many(self, requests):
        return [self.obtain(glyph, style) for glyph, style in requests]

    def obtain(self, glyph, style):
        key = RenderCache.key('provider', IMPORT_VERSION, glyph,
                              self.config.identity() | {'style': style})
        cache = self.cache_dir / 'providers'
        cache.mkdir(parents=True, exist_ok=True)
        target = cache / (key + '.svg')
        if target.exists():
            data = target.read_bytes()
            try:
                import_svg(data)  # Revalidate cached interchange.
            except XSRError as error:
                raise XSRError('XSR-PROVIDER-SVG', str(error)) from error
            return data
        with tempfile.TemporaryDirectory(prefix='provider-', dir=cache) as directory:
            output = Path(directory).resolve() / 'glyph.svg'
            executable = shutil.which(self.config.executable) or self.config.executable
            if Path(executable).suffix.lower() in ('.cmd', '.bat'):
                raise XSRError('XSR-PROVIDER-CONFIG', 'shell wrappers are unsupported; configure an interpreter')
            argv = [executable, *self.config.prefix_args,
                    '--glyph', glyph, '--style', style, '--output', str(output)]
            if self.config.options:
                argv += ['--options-json', json.dumps(self.config.options, ensure_ascii=True, sort_keys=True)]
            try:
                process = subprocess.run(argv, shell=False, capture_output=True,
                                         timeout=self.config.timeout)
            except OSError as error:
                raise XSRError('XSR-PROVIDER-UNAVAILABLE', f'cannot start provider: {error}') from error
            except subprocess.TimeoutExpired as error:
                raise XSRError('XSR-PROVIDER-FAILED', 'provider timed out') from error
            if process.returncode:
                # Code 3 is the optional missing-glyph convention; other nonzero
                # statuses remain failures, with a different typed diagnostic.
                code = 'XSR-PROVIDER-MISSING' if process.returncode == 3 else 'XSR-PROVIDER-FAILED'
                raise XSRError(code, f'provider exited {process.returncode}')
            if not output.is_file() or output.stat().st_size == 0:
                raise XSRError('XSR-PROVIDER-MISSING', 'provider produced no glyph')
            if output.stat().st_size > 2_000_000:
                raise XSRError('XSR-PROVIDER-SVG', 'provider output exceeds 2 MB')
            data = output.read_bytes()
            try:
                import_svg(data)
            except XSRError as error:
                raise XSRError('XSR-PROVIDER-SVG', str(error)) from error
            output.replace(target)
            # Result bytes are authoritative; metadata is optional, not guessed.
            target.with_suffix('.json').write_text(json.dumps({
                'svg_sha256': hashlib.sha256(data).hexdigest(), 'importer': IMPORT_VERSION,
                'provider': self.config.identity(), 'glyph': glyph, 'style': style},
                ensure_ascii=True, sort_keys=True), encoding='utf-8')
            return data
