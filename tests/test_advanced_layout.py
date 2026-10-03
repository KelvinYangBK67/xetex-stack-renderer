"""Cross-font EHFC semantics; assertions concern ink and relationships."""
import math
from dataclasses import replace
import pytest
from xsr.egyptian import HieropyAdapter, EgyptianLayoutError
from xsr.errors import XSRError
from xsr.ink import ink_mask


def text(*cps):
    return ''.join(map(chr,cps))

INSERTIONS = [
    ('ts',(0x13102,0x13432,0x133CF)),
    ('bs',(0x13193,0x13433,0x13000)),
    ('te',(0x13087,0x13434,0x133CF)),
    ('be',(0x1315C,0x13435,0x133CF)),
    ('m',(0x13219,0x13439,0x13283)),
    ('t',(0x13093,0x1343A,0x1340D)),
    ('b',(0x13098,0x1343B,0x1339B)),
]


def contained(result):
    assert 0 < result.width < 100 and 0 < result.height <= 1.081
    for g in (*result.glyphs,*result.decorations,*result.insertions):
        assert all(math.isfinite(v) for v in (g.x,g.y,g.width,g.height))
        assert g.width>0 and g.height>0
        assert g.x>=-1e-8 and g.y>=-1e-8
        assert g.x+g.width <= result.width+1e-8
        assert g.y+g.height <= result.height+1e-8
    assert all(math.isfinite(g.scale) and g.scale>0 for g in result.glyphs)


@pytest.mark.parametrize('slot,cps',INSERTIONS)
def test_insertion_regions_use_actual_empty_ink(font,slot,cps):
    result=HieropyAdapter().layout(text(*cps),font)
    contained(result)
    region,=result.insertions
    assert region.slot==slot
    # Independently rasterize only the host at twice the search resolution;
    # accepted child rectangles must be empty in that finer mask as well.
    host=replace(result,glyphs=result.glyphs[:1],insertions=(),decorations=())
    mask,unit=ink_mask(font,host,resolution=320,margin=0)
    rect=(math.ceil(region.x*unit),math.ceil(region.y*unit),
          math.floor((region.x+region.width)*unit),math.floor((region.y+region.height)*unit))
    assert mask.crop(rect).getbbox() is None
    child=result.glyphs[1]
    assert child.scale <= result.glyphs[0].scale
    if slot in ('ts','te','t'):
        assert region.y+region.height/2 < result.height*.60
    if slot in ('bs','be','b'):
        assert region.y+region.height/2 > result.height*.40


@pytest.mark.parametrize('cps',[
    (0x13102,0x13432,0x13437,0x13093,0x1343A,0x1340D,0x13438),
    (0x13102,0x13432,0x13437,0x133CF,0x13430,0x133CF,0x13438),
    (0x13193,0x13433,0x13000,0x13431,0x13153),
    (0x1309D,0x13436,0x1339B),
    (0x13379,0x1343C,0x13000,0x13431,0x13153,0x1343D,0x1337A),
    (0x13286,0x1343E,0x13153,0x1343F,0x13287),
    (0x13258,0x1343C,0x13153,0x1343D,0x1325B),
    (0x1343C,0x13153,0x1343D),
    (0x13000,0x13440,0x13455),
    (0x13153,0xFE00,0x13440),
    (0x13441,0x13442,0x13443,0x13444,0x13445,0x13446),
])
def test_advanced_combinations(font,cps):
    contained(HieropyAdapter().layout(text(*cps),font))


@pytest.mark.parametrize('selector,angle',[(0xFE00,90),(0xFE01,180),(0xFE02,270),(0xFE03,45),(0xFE04,135),(0xFE05,225),(0xFE06,315)])
def test_rotation_and_mirror(font,selector,angle):
    r=HieropyAdapter().layout(text(0x13153,selector,0x13440),font)
    g,=r.glyphs
    assert g.rotation==angle and g.mirror
    contained(r)
    if angle in (90,270):
        original=font.glyph(0x13153)
        assert g.width/g.height==pytest.approx(original.height/original.width)


@pytest.mark.parametrize('damage',range(1,16))
def test_all_damage_masks(font,damage):
    r=HieropyAdapter().layout(text(0x13000,0x13446+damage),font)
    assert len(r.decorations)==damage.bit_count()
    assert all(d.kind=='shade' for d in r.decorations)
    contained(r)


def test_advanced_parser_never_uses_hieropy_geometry(font,monkeypatch):
    from hieropy import unistructure as u
    def forbidden(*args,**kwargs):
        pytest.fail('Hieropy geometry or printing was used')
    for cls in (u.Group,u.Fragment,u.Literal,u.Horizontal,u.Vertical,u.Basic,u.Overlay,u.Enclosure,u.Blank,u.Lost):
        for method in ('size','format','fit','print'):
            if hasattr(cls,method):
                monkeypatch.setattr(cls,method,forbidden)
    for _,cps in INSERTIONS:
        contained(HieropyAdapter().layout(text(*cps),font))
    contained(HieropyAdapter().layout(text(0x13379,0x1343C,0x1309D,0x13436,0x1339B,0x1343D,0x1337A),font))


@pytest.mark.parametrize('cps,match',[
    ((0x13443,0xFE00),'continuous lost-sign'),
    ((0x13379,0x1343C,0x13000,0x1343F,0x13287),'mismatched enclosure'),
    ((0x13259,0x1343C,0x13000,0x1343D,0x1325D),'delimiter combination'),
])
def test_unsupported_semantics_fail_explicitly(font,cps,match):
    with pytest.raises(ValueError,match=match):
        HieropyAdapter().layout(text(*cps),font)


def test_no_insertion_space_is_an_error(tmp_path):
    from test_font_metrics import make_font
    from xsr.font_metrics import load_font
    path=tmp_path/'solid.ttf'
    make_font(path)
    with pytest.raises(XSRError,match='XSR-INSERTION-NO-SPACE'):
        HieropyAdapter().layout(text(0x13000,0x13439,0x13000),load_font(path))


def test_unseen_synthetic_hollow_font_supports_all_slots(tmp_path):
    from test_font_metrics import make_font
    from fontTools.ttLib import TTFont
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from xsr.font_metrics import load_font
    path=tmp_path/'unseen.ttf'
    make_font(path)
    font=TTFont(path)
    pen=TTGlyphPen(None)
    for points in [((0,0),(1000,0),(1000,1000),(0,1000)),
                   ((150,150),(150,850),(850,850),(850,150))]:
        pen.moveTo(points[0])
        for point in points[1:]: pen.lineTo(point)
        pen.closePath()
    font['glyf']['sign']=pen.glyph()
    font['hmtx']['sign']=(1000,0)
    font.save(path)
    profile=load_font(path)
    for control in (0x13432,0x13433,0x13434,0x13435,0x13439,0x1343A,0x1343B):
        result=HieropyAdapter().layout(text(0x13000,control,0x13000),profile)
        contained(result)
        assert len(result.insertions)==1
    nested=HieropyAdapter().layout(text(0x13000,0x13432,0x13437,0x13000,0x13435,0x13000,0x13438),profile)
    contained(nested)
    assert len(nested.insertions)==2
