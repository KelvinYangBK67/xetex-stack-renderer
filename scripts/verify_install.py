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
assert Path(xsr.__file__).is_relative_to(Path(sys.prefix)), 'verification must use the installed wheel'
expected_version = (Path(__file__).resolve().parents[1] / 'VERSION').read_text(encoding='utf-8').strip()
assert xsr.__version__ == metadata.version('xetex-stack-renderer') == expected_version
requirements = metadata.requires('xetex-stack-renderer') or []
assert not any('kage' in r.lower() or 'hieropy' in r.lower() for r in requirements)
assert EgyptianParser().parse(chr(0x13000))
assert KhitanParser().parse(chr(0x18B01))
assert r'\pgfpath' in glyph_tex(import_svg('<svg viewBox="0 0 200 200"><path d="M0 0H200V200H0Z"/></svg>'))
# Metadata-only raster/PDF resolution must work without test extras.
import tempfile
from PIL import Image
from pypdf import PdfWriter
from xsr.inline import GlyphRegistry, inline_tex
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)
    Image.new('RGB',(10,20),'white').save(root/'glyph.png')
    writer=PdfWriter();writer.add_blank_page(width=20,height=10)
    with (root/'glyph.pdf').open('wb') as stream:
        writer.write(stream)
    registry=GlyphRegistry(root)
    for extension in ('png','pdf'):
        registry.register(extension,'glyph.'+extension)
        assert r'\xsrInlineImage' in inline_tex(registry.resolve(extension))
assert not any(name.split('.')[0] == 'kage' for name in sys.modules)
if len(sys.argv) > 1:
    root = Path(sys.argv[1])
    renderer = default_renderer()
    assert renderer.render('egyptian', chr(0x13000), {'font_path': root/'tmp/fonts/NewGardiner.ttf'})
    assert renderer.render('khitan', chr(0x18B01), {'font_path': root/'tmp/fonts/NotoSerifKhitanSmallScript-Regular.ttf'})
files = metadata.files('xetex-stack-renderer') or []
assert not any(str(p).lower().endswith(('.ttf','.otf','.svg','.png','.jpg','.jpeg','.pdf','.dump','.kage')) for p in files)
print(f'XSR {expected_version} installed wheel: imports, native parsers, vectors, raster/PDF metadata and font rendering pass; no KAGE/Hieropy or bundled assets')
