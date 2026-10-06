import pytest
from xsr.errors import XSRError
from xsr.font_metrics import load_font
from xsr.synthetic import FallbackFont, XSRWarning
from xsr.egyptian import EgyptianParser
from xsr.egyptian.backend import EgyptianBackend
from xsr.khitan.backend import KhitanBackend
from test_font_metrics import make_font


def test_nominal_metrics_and_outline(tmp_path):
    path = tmp_path/'synthetic.ttf'
    make_font(path)
    font = FallbackFont(load_font(path))
    with pytest.warns(XSRWarning, match='XSR-GLYPH-MISSING'):
        metric = font.glyph(0x13002)
    assert metric.bounds == (0,0,1,1)
    assert metric.advance == 1
    assert len(font.outline(0x13002)) == 10
    with pytest.raises(XSRError, match='XSR-GLYPH-MISSING'):
        FallbackFont(load_font(path), 'error').glyph(0x13002)
    # Existing empty-outline diagnostics are not mislabeled as a missing glyph.
    with pytest.raises(XSRError, match='XSR-GLYPH-EMPTY'):
        font.glyph(0x13001)


@pytest.mark.parametrize('join', [0x13430,0x13431])
def test_egyptian_hv_missing_and_controls(tmp_path, join):
    path = tmp_path/'synthetic.ttf'
    make_font(path)
    text = chr(0x13000)+chr(join)+chr(0x13002)
    with pytest.warns(XSRWarning, match='XSR-GLYPH-MISSING') as warnings:
        tex = EgyptianBackend().render(text, {'font_path': path})
    assert len(warnings) == 1
    assert tex.count('xsrEgyptianSynthetic') == 1
    assert tex.count('xsrEgyptianGlyph') == 1
    with pytest.raises(XSRError, match='XSR-GLYPH-MISSING'):
        EgyptianBackend().render(text, {'font_path': path, 'missing_glyph_policy': 'error'})
    # Registered variation selector affects geometry; never measured as a glyph.
    font = FallbackFont(load_font(path))
    with pytest.warns(XSRWarning):
        layout = EgyptianParser().layout(chr(0x131B1)+chr(0xFE00), font)
    assert font.missing == {0x131B1}
    assert layout.width > 0 and layout.height > 0


def test_khitan_control_exclusion(tmp_path):
    path = tmp_path/'synthetic.ttf'
    make_font(path)
    text = chr(0x18B01)+chr(0x16FE4)+chr(0x18CFF)+' '+chr(0x18B01)+chr(0x200B)+chr(0x18B01)
    with pytest.warns(XSRWarning) as warnings:
        result = KhitanBackend().render(text, {'font_path': path})
    assert len(warnings) == 2
    assert result.count('xsrKhitanSynthetic') == 4
    assert r'\xsrKhitanLayout{1}{2}{0}{2}' in result
