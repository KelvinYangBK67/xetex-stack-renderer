"""Reference fonts are test inputs, never layout dependencies.

XSR_TEST_FONTS is an os.pathsep-separated list of additional local fonts.
XSR_NOTO_FONT overrides the downloaded reference font location.
"""
import os
from pathlib import Path
import hieropy
import pytest
from xsr.font_metrics import load_font, tex_font_path

ROOT = Path(__file__).resolve().parents[1]
NEW_GARDINER = Path(hieropy.__file__).parent / 'resources/NewGardiner.ttf'
NOTO = Path(os.environ.get('XSR_NOTO_FONT', ROOT / 'tmp/fonts/NotoSansEgyptianHieroglyphs-Regular.ttf'))
FONTS = [NEW_GARDINER]
if NOTO.is_file():
    FONTS.append(NOTO)
if Path('C:/Windows/Fonts/seguihis.ttf').is_file():
    FONTS.append(Path('C:/Windows/Fonts/seguihis.ttf'))
FONTS += [Path(p) for p in os.environ.get('XSR_TEST_FONTS', '').split(os.pathsep) if p]

@pytest.fixture(params=FONTS, ids=lambda p: p.stem)
def font(request):
    return load_font(request.param)

@pytest.fixture
def font_options():
    profile = load_font(NEW_GARDINER)
    return {'font_path': tex_font_path(profile.path), 'font_digest': profile.digest}
