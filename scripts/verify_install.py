"""Run with a freshly installed wheel; reject external-engine dependencies."""
import importlib.abc
from importlib import metadata
from pathlib import Path
import sys


class NoEngine(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0].lower() in ('kage', 'hieropy'):
            raise AssertionError(f'XSR attempted to import external engine {fullname}')


sys.meta_path.insert(0, NoEngine())
import xsr
from xsr.egyptian import EgyptianParser
from xsr.khitan import KhitanParser
from xsr.vector import import_svg, glyph_tex
from xsr.renderer import default_renderer
assert xsr.__version__ == metadata.version('xetex-stack-renderer') == '0.9'
requirements = metadata.requires('xetex-stack-renderer') or []
assert not any('kage' in r.lower() or 'hieropy' in r.lower() for r in requirements)
assert EgyptianParser().parse(chr(0x13000))
assert KhitanParser().parse(chr(0x18B01))
assert r'\pgfpath' in glyph_tex(import_svg('<svg viewBox="0 0 200 200"><path d="M0 0H200V200H0Z"/></svg>'))
assert not any(name.split('.')[0] == 'kage' for name in sys.modules)
if len(sys.argv) > 1:
    root = Path(sys.argv[1])
    renderer = default_renderer()
    assert renderer.render('egyptian', chr(0x13000), {'font_path': root/'tmp/fonts/NewGardiner.ttf'})
    assert renderer.render('khitan', chr(0x18B01), {'font_path': root/'tmp/fonts/NotoSerifKhitanSmallScript-Regular.ttf'})
files = metadata.files('xetex-stack-renderer') or []
assert not any(str(p).lower().endswith(('.ttf','.otf','.svg','.dump','.kage')) for p in files)
print('XSR 0.9 installed wheel: imports, native parsers, vectors and font rendering pass; no KAGE/Hieropy or bundled assets')
