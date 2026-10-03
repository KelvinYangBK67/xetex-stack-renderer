from pathlib import Path
import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from xsr.font_metrics import FontMetrics, load_font
from xsr.egyptian import HieropyAdapter
from xsr.renderer import default_renderer
from conftest import FONTS


def make_font(path, upem=1000, width=600):
    """A deliberately unfamiliar font: negative bearing, descender, wide advance."""
    fb = FontBuilder(upem, isTTF=True)
    fb.setupGlyphOrder(['.notdef', 'sign', 'empty'])
    fb.setupCharacterMap({0x13000: 'sign', 0x13001: 'empty'})
    pen = TTGlyphPen(None)
    pen.moveTo((-upem / 10, -upem / 5))
    pen.lineTo((width - upem / 10, -upem / 5))
    pen.lineTo((width - upem / 10, upem * .7))
    pen.lineTo((-upem / 10, upem * .7))
    pen.closePath()
    empty = TTGlyphPen(None).glyph()
    fb.setupGlyf({'.notdef': empty, 'sign': pen.glyph(), 'empty': empty})
    fb.setupHorizontalMetrics({'.notdef': (upem, 0), 'sign': (upem, -upem // 10), 'empty': (upem, 0)})
    fb.setupHorizontalHeader(ascent=upem, descent=-upem // 4)
    fb.setupNameTable({'familyName': 'XSR Synthetic', 'styleName': 'Regular', 'psName': 'XSRSynthetic-Regular'})
    fb.setupOS2(sTypoAscender=upem, sTypoDescender=-upem // 4, usWinAscent=upem, usWinDescent=upem // 4)
    fb.setupPost()
    fb.setupMaxp()
    fb.save(path)


def test_units_and_true_ink_bounds(tmp_path):
    metrics = []
    for upem in (1000, 2000):
        path = tmp_path / f'font-{upem}.ttf'
        make_font(path, upem, upem * .6)
        font = FontMetrics(path)
        assert font.units_per_em == upem
        g = font.glyph(0x13000)
        assert g.bounds == pytest.approx((-.1, -.2, .5, .7))
        assert g.advance == 1
        assert g.width == pytest.approx(.6)
        assert g.height == pytest.approx(.9)
        assert font.ascender == 1 and font.descender == -.25
        assert font.outline(0x13000)[0] == ('moveTo', ((-.1, -.2),))
        metrics.append(HieropyAdapter().layout(chr(0x13000), font))
    assert metrics[0] == metrics[1]


def test_loading_errors(tmp_path):
    with pytest.raises(ValueError, match='cannot load font'):
        FontMetrics(tmp_path / 'missing.ttf')
    bad = tmp_path / 'bad.ttf'
    bad.write_text('not a font')
    with pytest.raises(ValueError, match='cannot load font'):
        FontMetrics(bad)
    make_font(bad)
    font = FontMetrics(bad)
    with pytest.raises(ValueError, match='no glyph'):
        font.glyph(0x13153)
    with pytest.raises(ValueError, match='no outline'):
        font.glyph(0x13001)


def test_font_loading_and_outlines(font):
    assert font.units_per_em > 0
    assert len(font.digest) == 32
    g = font.glyph(0x13000)
    assert g.width > 0 and g.height > 0 and g.advance > 0
    assert font.outline(0x13000)


def test_reference_fonts_change_geometry():
    if len(FONTS) < 2:
        pytest.skip('install a second reference font or set XSR_TEST_FONTS')
    layouts = [HieropyAdapter().layout(chr(0x13000) + chr(0x13431) + chr(0x13153), load_font(p)) for p in FONTS]
    assert len(set(layouts)) > 1


def test_replaced_font_invalidates_cache(tmp_path):
    path = tmp_path / 'font.ttf'
    make_font(path)
    font = load_font(path)
    renderer = default_renderer(tmp_path / 'cache')
    first = renderer.render('egyptian', chr(0x13000), {'font_path': str(path)})
    make_font(path, width=800)
    second = renderer.render('egyptian', chr(0x13000), {'font_path': str(path)})
    assert first != second
    assert len(list((tmp_path / 'cache').glob('*.tex'))) == 2
    with pytest.raises(ValueError, match='digest mismatch'):
        renderer.render('egyptian', chr(0x13000), {'font_path': str(path), 'font_digest': font.digest})


def test_explicit_font_is_required():
    with pytest.raises(ValueError, match='explicit font_path'):
        default_renderer().render('egyptian', chr(0x13000))


def test_cff_outline_bounds(tmp_path):
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder(['.notdef', 'sign'])
    fb.setupCharacterMap({0x13000: 'sign'})
    pen = T2CharStringPen(800, None)
    pen.moveTo((0, 0))
    pen.curveTo((0, 1000), (600, 1000), (600, 0))
    pen.closePath()
    fb.setupCFF('XSRCFF-Regular', {'FullName': 'XSR CFF', 'FamilyName': 'XSR CFF', 'Weight': 'Regular'},
                {'.notdef': T2CharStringPen(800, None).getCharString(), 'sign': pen.getCharString()}, {})
    fb.setupHorizontalMetrics({'.notdef': (800, 0), 'sign': (800, 0)})
    fb.setupHorizontalHeader(ascent=1000, descent=0)
    fb.setupNameTable({'familyName': 'XSR CFF', 'styleName': 'Regular'})
    fb.setupOS2(sTypoAscender=1000, sTypoDescender=0, usWinAscent=1000, usWinDescent=0)
    fb.setupPost()
    path = tmp_path / 'cff.otf'
    fb.save(path)
    font = FontMetrics(path)
    # Cubic control points reach 1 em, but the true Bezier extremum is .75 em.
    assert font.glyph(0x13000).bounds == pytest.approx((0, 0, .6, .75))
    assert any(op == 'curveTo' for op, _ in font.outline(0x13000))


def test_tex_path_validation(tmp_path):
    from xsr.font_metrics import tex_font_path
    assert 'font with spaces.ttf' in tex_font_path(tmp_path / 'font with spaces.ttf')
    with pytest.raises(ValueError, match='font path'):
        tex_font_path(tmp_path / 'font{injection}.ttf')
