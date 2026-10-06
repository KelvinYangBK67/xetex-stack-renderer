"""Unicode-driven 0.6 semantics and horizontal layout contracts."""
from dataclasses import replace
import pytest
from xsr.egyptian import EgyptianParser
from xsr.egyptian.layout import EgyptianLayout
from xsr.egyptian.model import EgyptianNode, ParsedEgyptianRun
from xsr.egyptian.semantics import rotation, validate_mirror, layout_options
from xsr.egyptian.unicode_data import ROTATIONS, NO_MIRROR, NO_ROTATE
from xsr.egyptian.source import source_runs
from xsr import build_default_registry
from test_advanced_layout import text, contained, INSERTIONS


@pytest.mark.parametrize('pair,angle',sorted(ROTATIONS.items()))
def test_every_registered_rotation(pair,angle):
    base,vs=pair
    assert rotation(base,vs-0xFE00+1)==angle
    node=EgyptianParser().parse(text(base,vs)).structure.children[0]
    assert node.rotation==angle


@pytest.mark.parametrize('base',sorted(NO_MIRROR))
def test_no_mirror(base):
    with pytest.raises(ValueError,match='XSR-NO-MIRROR'):
        validate_mirror(base,True)


@pytest.mark.parametrize('base',sorted(NO_ROTATE))
def test_no_rotate_except_registered_variants(base):
    for vs in range(0xFE00,0xFE07):
        if (base,vs) not in ROTATIONS:
            with pytest.raises(ValueError,match='XSR-NO-ROTATE'):
                rotation(base,vs-0xFE00+1)


@pytest.mark.parametrize('base,vs',[(0x13000,0xFE00),(0x13153,0xFE03),(0x13399,0xFE02),(0x13419,0xFE04)])
def test_unregistered_rotation_is_not_guessed(base,vs):
    with pytest.raises(ValueError,match='XSR-VARIANT-UNREGISTERED'):
        EgyptianParser().parse(text(base,vs))


def test_same_selector_different_registered_angles():
    assert [rotation(cp,4) for cp in (0x13012,0x130B8,0x1312F,0x13419)]==[30,25,40,15]


@pytest.mark.parametrize('angle',[45,90,135,180,225,270,315])
def test_geometry_primitive_retains_all_angles(font,angle):
    node=EgyptianNode('run',(EgyptianNode('sign',codepoint=0x13153,rotation=angle,mirror=True),))
    contained(EgyptianLayout(font).layout(ParsedEgyptianRun('','synthetic',node)))


@pytest.mark.parametrize('slot,cps',INSERTIONS)
def test_rtl_insertion_uses_logical_start_end(font,slot,cps):
    parser=EgyptianParser()
    ltr=parser.layout(text(*cps),font)
    rtl=parser.layout(text(*cps),font,direction='rtl')
    contained(rtl)
    a,b=ltr.insertions[-1],rtl.insertions[-1]
    assert a.slot==b.slot==slot
    assert b.x+b.width/2==pytest.approx(rtl.width-a.x-a.width/2,abs=.025)
    assert all(g.mirror for g in rtl.glyphs)


def test_rtl_top_level_and_nested_order(font):
    s=text(0x13000,0x13431,0x13050,0x13430,0x13153,0x133CF)
    ltr=EgyptianParser().layout(s,font)
    rtl=EgyptianParser().layout(s,font,direction='rtl')
    assert rtl.glyphs[0].codepoint==0x133CF
    bycp={g.codepoint:g for g in rtl.glyphs}
    for g in ltr.glyphs:
        mirrored=bycp[g.codepoint]
        assert mirrored.x==pytest.approx(rtl.width-g.x-g.width)
        assert mirrored.y==pytest.approx(g.y)


def test_rtl_rotation_is_reflection_after_logical_rotation(font):
    s=text(0x13012,0xFE03)
    a=EgyptianParser().layout(s,font).glyphs[0]
    b=EgyptianParser().layout(s,font,direction='rtl').glyphs[0]
    c=EgyptianParser().layout(s+chr(0x13440),font,direction='rtl').glyphs[0]
    assert a.rotation==b.rotation==c.rotation==30
    assert not a.mirror and b.mirror and not c.mirror
    assert b.ink_left==pytest.approx(-a.ink_left-a.width/a.scale)


@pytest.mark.parametrize('direction',['ltr','rtl'])
@pytest.mark.parametrize('pair',[(None,None),(0x13379,None),(None,0x1337A),(0x13259,0x1325D),(0x13288,0x13289),(0x1342F,0x1337B)])
def test_enclosure_endpoints(font,direction,pair):
    a,b=pair
    walled=a==0x13288
    seq=([a,0x13447] if a else [])+[0x1343E if walled else 0x1343C,0x13000,0x1343F if walled else 0x1343D]+([b,0x13455] if b else [])
    if a==0x1342F and a not in font._cmap:
        from xsr.synthetic import FallbackFont, XSRWarning
        with pytest.raises(ValueError,match='XSR-GLYPH-MISSING'):
            EgyptianParser().layout(text(*seq),FallbackFont(font, 'error'),direction=direction)
        with pytest.warns(XSRWarning, match='XSR-GLYPH-MISSING'):
            fallback = EgyptianParser().layout(text(*seq),font,direction=direction)
        contained(fallback)
        assert len(fallback.glyphs) == 3
        return
    r=EgyptianParser().layout(text(*seq),font,direction=direction)
    contained(r)
    if a or b:
        assert any(d.kind=='shade' for d in r.decorations)
    if pair==(0x13379,None):
        assert r.decorations[0].ends==(True,False)
        assert r.decorations[0].mirror==(direction=='rtl')


@pytest.mark.parametrize('a,b',[(0x13443,0x13443),(0x13444,0x13444),(0x13445,0x13445),(0x13446,0x13446)])
@pytest.mark.parametrize('joiner',[None,0x13431,0x13430])
def test_continuous_shading_has_no_gap(font,a,b,joiner):
    cps=[a,0xFE00]+([joiner] if joiner else [])+[b,0xFE00]
    r=EgyptianParser().layout(text(*cps),font)
    x,y=r.decorations
    if joiner==0x13430:
        assert x.y+x.height==pytest.approx(y.y)
    else:
        assert x.x+x.width==pytest.approx(y.x)
    ordinary=EgyptianParser().layout(text(a,*([joiner] if joiner else []),b),font)
    x,y=ordinary.decorations
    assert (y.y-x.y-x.height if joiner==0x13430 else y.x-x.x-x.width)>0


@pytest.mark.parametrize('brackets',['[]','{}','\u2e22\u2e23','\u27e8\u27e9','\u27e6\u27e7'])
def test_brackets_in_quadrats(font,brackets):
    s=brackets[0]+text(0x13000,0x13431,0x13050)+brackets[1]
    r=EgyptianParser().layout(s,font)
    contained(r)
    assert len(r.glyphs)==2
    assert len(r.decorations)==2
    assert all(d.kind.startswith('bracket-') for d in r.decorations)


def test_brackets_are_explicit_context_not_global_punctuation():
    reg=build_default_registry()
    assert not list(reg.script_runs('[Latin] {ordinary}'))
    s=r'\xsrEgyptianText{['+text(0x13000,0x13431,0x13050)+r']} outside [Latin]'
    run,=source_runs(s,reg)
    assert run.text.startswith('[') and run.text.endswith(']')


def test_writing_mode_is_reserved():
    with pytest.raises(ValueError,match='XSR-WRITING-MODE-UNSUPPORTED'):
        layout_options({'writing_mode':'vertical'})
    with pytest.raises(ValueError,match='XSR-DIRECTION'):
        layout_options({'direction':'diagonal'})

@pytest.mark.parametrize('direction',['ltr','rtl'])
def test_empty_enclosure_and_redundant_segment(font,direction):
    a=EgyptianParser()
    contained(a.layout(text(0x13379,0x1343C,0x1343D,0x1337A),font,direction=direction))
    assert a.layout(text(0x13437,0x13000,0x13438),font,direction=direction)==a.layout(text(0x13000),font,direction=direction)


def test_unicode_complex_editorial_brackets(font):
    s='['+text(0x1308B,0x13430,0x133CF,0x13431)+'['+text(0x133E5)
    r=EgyptianParser().layout(s,font)
    contained(r)
    assert len(r.decorations)==2 and len(r.glyphs)==3


def test_unregistered_high_selector():
    with pytest.raises(ValueError,match='XSR-VARIANT-UNREGISTERED'):
        EgyptianParser().parse(text(0x13000,0xFE07))


def test_mixed_lost_spacing_and_phase(font):
    a=EgyptianParser()
    regular=a.layout(text(0x13443,0x13443),font)
    mixed=a.layout(text(0x13443,0xFE00,0x13443),font)
    continuous=a.layout(text(0x13443,0xFE00,0x13443,0xFE00),font)
    assert continuous.width < mixed.width < regular.width
    parsed=a.parse(text(0x13443,0xFE00,0x13443,0xFE00))
    units=EgyptianLayout(font).quadrats(parsed)
    assert units[1].decorations[0].phase==pytest.approx(units[0].width)

@pytest.mark.parametrize('brackets',['[[', '[{', '\u27e8['])
def test_consecutive_editorial_brackets_are_preserved(font,brackets):
    r=EgyptianParser().layout(brackets+text(0x13000)+']]',font)
    contained(r)
    assert len(r.decorations)==4
    assert [d.kind for d in r.decorations[:2]]==['bracket-'+str(ord(c)) for c in brackets]


def test_direction_is_part_of_cache_identity(font,tmp_path):
    from xsr.renderer import default_renderer
    renderer=default_renderer(tmp_path)
    options={'font_path':str(font.path)}
    a=renderer.render('egyptian',text(0x13000,0x13050),options)
    b=renderer.render('egyptian',text(0x13000,0x13050),options | {'direction':'rtl'})
    assert a!=b
    assert r'\xsrEgyptianFlow{ltr}' in a
    assert r'\xsrEgyptianFlow{rtl}' in b
    assert renderer.render('egyptian',text(0x13000,0x13050),options)==a
