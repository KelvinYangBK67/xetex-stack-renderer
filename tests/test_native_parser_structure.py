"""Direct structural and validation contracts for XSR's native EHFC parser."""
from dataclasses import replace
import pytest
from xsr.egyptian import EgyptianParser, EgyptianParseError
from xsr.egyptian.model import EgyptianNode

A,B,C,D = 0x13000,0x13050,0x13153,0x133CF
H,V,O,SB,SE = 0x13431,0x13430,0x13436,0x13437,0x13438
ENC_START = 0x1343C

def chars(*cps):
    return ''.join(map(chr,cps))

def nodes(*cps):
    return EgyptianParser().parse(chars(*cps)).structure.children

def sign(cp, **kw):
    return EgyptianNode('sign',codepoint=cp,**kw)

def group(kind,*parts):
    return EgyptianNode(kind,parts)

def test_single_and_long_plain_run():
    assert nodes(A) == (sign(A),)
    assert nodes(*([A,B,C,D]*20)) == tuple(sign(c) for c in [A,B,C,D]*20)

@pytest.mark.parametrize('cps,expected',[
    ((A,H,B),group('horizontal',sign(A),sign(B))),
    ((A,V,B),group('vertical',sign(A),sign(B))),
    ((A,H,B,V,C),group('vertical',group('horizontal',sign(A),sign(B)),sign(C))),
    ((A,H,SB,B,V,C,SE),group('horizontal',sign(A),group('vertical',sign(B),sign(C)))),
    ((SB,SB,A,SE,SE),sign(A)),
    ((A,O,B),group('overlay',group('horizontal',sign(A)),group('vertical',sign(B)))),
    ((SB,A,H,B,SE,O,SB,C,V,D,SE),group('overlay',
      group('horizontal',group('horizontal',sign(A),sign(B))),
      group('vertical',group('vertical',sign(C),sign(D))))),
])
def test_operator_tree(cps,expected):
    assert nodes(*cps) == (expected,)

@pytest.mark.parametrize('cp,slot',[(0x13432,'ts'),(0x13433,'bs'),(0x13434,'te'),
    (0x13435,'be'),(0x13439,'m'),(0x1343A,'t'),(0x1343B,'b')])
def test_each_insertion_slot(cp,slot):
    assert nodes(A,cp,B) == (EgyptianNode('insertion',(sign(A),sign(B)),slots=(slot,)),)

def test_nested_and_combined_insertion():
    inner = EgyptianNode('insertion',(sign(B),sign(C)),slots=('be',))
    outer = EgyptianNode('insertion',(sign(A),inner),slots=('ts',))
    assert nodes(A,0x13432,SB,B,0x13435,C,SE) == (outer,)
    assert nodes(A,H,B,0x13434,C,V,D) == (
        group('vertical',group('horizontal',sign(A),
          EgyptianNode('insertion',(sign(B),sign(C)),slots=('te',))),sign(D)),)
    assert nodes(A,0x13432,B,0x13433,C)[0].slots == ('ts','bs')

@pytest.mark.parametrize('opening,begin,end,closing,kind',[
    (0x13379,0x1343C,0x1343D,0x1337A,'cartouche'),
    (0x13258,0x1343C,0x1343D,0x1325B,'rectangle'),
    (0x13286,0x1343E,0x1343F,0x13287,'walled'),
    (0x13259,0x1343C,0x1343D,0x1325D,'rectangle'),
    (0x13288,0x1343E,0x1343F,0x13289,'walled'),
    (0x1342F,0x1343C,0x1343D,0x1337B,'cartouche'),
    (None,0x1343C,0x1343D,None,'cartouche'),
])
def test_enclosure_classes_and_endpoints(opening,begin,end,closing,kind):
    cps=([opening] if opening else [])+[begin,A,H,B,end]+([closing] if closing else [])
    node,=nodes(*cps)
    assert node.kind == 'enclosure'
    assert node.children == (group('horizontal',sign(A),sign(B)),)
    assert node.enclosure == kind
    assert node.endpoint_codepoints == (opening,closing)
    assert node.ends == (opening is not None,closing is not None)

def test_nested_and_empty_enclosures_and_damage():
    outer,=nodes(0x13379,0x13447,0x1343C,A,0x1343C,B,0x1343D,
                 0x1343D,0x1337A,0x13455)
    assert outer.children[1].kind == 'enclosure'
    assert outer.endpoint_damage == (1,15)
    empty,=nodes(0x1343E,0x1343F)
    assert empty.children == (EgyptianNode('blank',size=(1,1)),)

def test_modifiers_and_direction_independence():
    text=chars(0x13012,0xFE03,0x13440,0x13455)
    parsed=EgyptianParser().parse(text)
    assert parsed.structure.children == (sign(0x13012,rotation=30,mirror=True,damage=15),)
    assert EgyptianParser().parse(text).structure == parsed.structure

@pytest.mark.parametrize('mask',range(1,16))
def test_all_damage_controls(mask):
    assert nodes(A,0x13446+mask) == (sign(A,damage=mask),)

@pytest.mark.parametrize('cp,size',[
    (0x13441,(1,1)),(0x13442,(.5,.5)),(0x13443,(1,1)),
    (0x13444,(.5,.5)),(0x13445,(.5,1)),(0x13446,(1,.5))])
def test_blank_and_lost(cp,size):
    node,=nodes(cp)
    assert node.kind == ('blank' if cp<0x13443 else 'lost')
    assert node.size == size
    if cp>=0x13443:
        assert nodes(cp,0xFE00) == (replace(node,continuous=True),)

@pytest.mark.parametrize('left,right',[(ord('['),ord(']')),(ord('{'),ord('}')),
    (0x2E22,0x2E23),(0x27E8,0x27E9),(0x27E6,0x27E7)])
def test_editorial_brackets(left,right):
    node,=nodes(left,A,H,B,right)
    assert node.kind == 'horizontal'
    assert node.children == (EgyptianNode('bracket',codepoint=left),sign(A),
                             sign(B),EgyptianNode('bracket',codepoint=right))
    assert len(nodes(left,left,A,right,right)[0].children) == 5

@pytest.mark.parametrize('cps,part',[
    ((A,H),'Unexpected end'),((A,V),'Unexpected end'),
    ((A,H,V,B),'without a preceding'),((H,A),'without a preceding'),
    ((0x13432,A),'without a preceding'),((A,0x13432),'Unexpected end'),
    ((O,A),'without a preceding'),((A,O),'Unexpected end'),
    ((SB,A),'unclosed segment'),((SE,A),'unmatched closing'),
    ((SB,SE),'empty segment'),((ENC_START,A),'unclosed enclosure'),
    ((ENC_START,A,0x1343F),'mismatched enclosure'),
    ((0x13440,A),'mirror without'),((0x13447,A),'damage without'),
    ((0xFE00,A),'variation selector without'),
    ((A,0x13455,0x13440),'mirror without'),
    ((A,0x13447,0x13455),'damage without'),
    ((A,0x13440,0x13440),'mirror without'),
    ((0x13012,0xFE03,0xFE03),'variation selector without'),
    ((SB,A,ENC_START,B,SE,0x1343D),'unmatched closing'),
    ((0x13288,ENC_START,A,0x1343D,0x1325D),'control family'),
    ((A,0x13456),'reserved character'),
])
def test_malformed_ehfc(cps,part):
    with pytest.raises(EgyptianParseError,match=part):
        nodes(*cps)

def test_unregistered_rotation_and_no_mirror():
    with pytest.raises(ValueError,match='XSR-VARIANT-UNREGISTERED'):
        nodes(A,0xFE00)
    with pytest.raises(ValueError,match='XSR-NO-MIRROR'):
        nodes(0x130BB,0x13440)
