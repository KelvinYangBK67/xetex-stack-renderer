"""Native EHFC parser producing XSR's immutable EgyptianNode tree.

Unicode 18 chapter 11.4.2 defines precedence: insertion, overlay,
horizontal join, vertical join. Segment controls group recursively; adjacent
complete expressions are separate quadrats. Joiners associate to the left.
"""
from __future__ import annotations
from ..errors import XSRError
from ..font_metrics import FontMetrics
from .layout import EgyptianLayout
from .model import EgyptianNode, ParsedEgyptianRun, RenderResult
from .semantics import layout_options, rotation, validate_mirror

PARSER_VERSION = '0.7'
V, H, O, SB, SE = 0x13430, 0x13431, 0x13436, 0x13437, 0x13438
INSERT = {0x13432:'ts',0x13433:'bs',0x13434:'te',0x13435:'be',
          0x13439:'m',0x1343A:'t',0x1343B:'b'}
OPEN, CLOSE, WALL, END_WALL = 0x1343C, 0x1343D, 0x1343E, 0x1343F
BRACKETS = frozenset(map(ord, '[]{}\u2e22\u2e23\u27e8\u27e9\u27e6\u27e7'))
PLAIN_START = frozenset((0x13258,0x13259,0x1325A,0x13379,0x1342F))
PLAIN_END = frozenset((0x1325B,0x1325C,0x1325D,0x13282,0x1337A,0x1337B))
WALL_START = frozenset((0x13286,0x13288))
WALL_END = frozenset((0x13287,0x13289))
ENDPOINTS = PLAIN_START | PLAIN_END | WALL_START | WALL_END

class EgyptianParseError(XSRError):
    def __init__(self, text: str, detail: str, offset: int | None = None):
        self.text, self.detail, self.offset = text, detail, offset
        cps = ' '.join(f'U+{ord(c):05X}' for c in text)
        where = '' if offset is None else f' at character {offset + 1}'
        super().__init__('XSR-PARSE', f'Egyptian EHFC parse error{where} [{cps}]: {detail}')

def _sign(cp):
    return cp is not None and (0x13000 <= cp <= 0x1342F or 0x13460 <= cp <= 0x143FF)

def _group(kind, nodes):
    return nodes[0] if len(nodes) == 1 else EgyptianNode(kind, tuple(nodes))

class _Reader:
    def __init__(self, text):
        self.text, self.chars, self.pos = text, tuple(map(ord,text)), 0

    def peek(self, ahead=0):
        i = self.pos + ahead
        return self.chars[i] if i < len(self.chars) else None

    def take(self):
        cp = self.peek()
        if cp is None: self.fail('Unexpected end of input')
        self.pos += 1
        return cp

    def fail(self, detail):
        raise EgyptianParseError(self.text, detail, self.pos)

    def sequence(self, stop=frozenset()):
        out = []
        while self.peek() is not None and self.peek() not in stop:
            out.append(self.vertical())
        return out

    def vertical(self):
        parts = [self.horizontal()]
        while self.peek() == V:
            self.take()
            parts.append(self.horizontal())
        return _group('vertical', parts)

    def horizontal(self):
        parts = [self.overlay()]
        while True:
            cp = self.peek()
            if cp == H:
                self.take()
                parts.append(self.overlay())
            elif cp in BRACKETS or (parts[-1].kind == 'bracket' and self.primary_start(cp)):
                parts.append(self.overlay())
            else: break
        return _group('horizontal', parts)

    def overlay(self):
        parts = [self.insertion()]
        while self.peek() == O:
            self.take()
            parts.append(self.insertion())
        if len(parts) == 1: return parts[0]
        return EgyptianNode('overlay', (
            EgyptianNode('horizontal', tuple(parts[:1])),
            EgyptianNode('vertical', tuple(parts[1:]))))

    def insertion(self):
        core = self.primary()
        slots, children = [], [core]
        while self.peek() in INSERT:
            if core.kind not in ('sign','insertion'):
                self.fail('insertion requires a sign core')
            slot = INSERT[self.take()]
            if slot in slots: self.fail(f'duplicate {slot} insertion')
            slots.append(slot)
            children.append(self.primary())
        return EgyptianNode('insertion',tuple(children),slots=tuple(slots)) if slots else core

    @staticmethod
    def primary_start(cp):
        return (_sign(cp) or cp in BRACKETS or
                cp in (SB,OPEN,WALL) or cp is not None and 0x13441 <= cp <= 0x13446)

    def primary(self):
        cp = self.peek()
        if cp is None: self.fail('Unexpected end of input')
        if cp in BRACKETS:
            self.take()
            return EgyptianNode('bracket',codepoint=cp)
        if cp == SB:
            self.take()
            parts = self.sequence(frozenset((SE,)))
            if self.peek() != SE: self.fail('unclosed segment')
            self.take()
            if not parts: self.fail('empty segment')
            return _group('run',parts)
        if cp in (OPEN,WALL):
            return self.enclosure(None,0)
        if cp in (0x13441,0x13442):
            self.take()
            d = 1 if cp == 0x13441 else .5
            return EgyptianNode('blank',size=(d,d))
        if 0x13443 <= cp <= 0x13446:
            self.take()
            size = {0x13443:(1,1),0x13444:(.5,.5),0x13445:(.5,1),0x13446:(1,.5)}[cp]
            continuous = self.peek() == 0xFE00
            if continuous: self.take()
            elif self.peek() is not None and 0xFE01 <= self.peek() <= 0xFE0F:
                raise XSRError('XSR-VARIANT-UNREGISTERED','lost signs only support FE00 continuous shading')
            return EgyptianNode('lost',size=size,continuous=continuous)
        if _sign(cp):
            self.take()
            selector = 0
            if self.peek() is not None and 0xFE00 <= self.peek() <= 0xFE0F:
                selector = self.take()-0xFE00+1
            angle = rotation(cp,selector)
            mirror = self.peek() == 0x13440
            if mirror: self.take()
            validate_mirror(cp,mirror)
            damage = 0
            if self.peek() is not None and 0x13447 <= self.peek() <= 0x13455:
                damage = self.take()-0x13446
            if cp in ENDPOINTS and self.peek() in (OPEN,WALL):
                if angle or mirror: self.fail('invalid enclosure endpoint modifier')
                return self.enclosure(cp,damage)
            return EgyptianNode('sign',codepoint=cp,rotation=angle,mirror=mirror,damage=damage)
        if cp in (SE,CLOSE,END_WALL): self.fail('unmatched closing control')
        if cp in (V,H,O) or cp in INSERT: self.fail('joiner or insertion control without a preceding operand')
        if cp == 0x13440: self.fail('mirror without a preceding sign')
        if 0x13447 <= cp <= 0x13455: self.fail('damage without a valid target')
        if 0xFE00 <= cp <= 0xFE0F: self.fail('variation selector without a valid sign')
        self.fail(f'unsupported or reserved character U+{cp:05X}')

    def enclosure(self, opening, opening_damage):
        control = self.take()
        end = END_WALL if control == WALL else CLOSE
        parts = self.sequence(frozenset((CLOSE,END_WALL)))
        if self.peek() != end:
            self.fail('mismatched enclosure controls' if self.peek() in (CLOSE,END_WALL)
                      else 'unclosed enclosure control')
        self.take()
        closing = self.peek() if self.peek() in ENDPOINTS else None
        closing_damage = 0
        if closing is not None:
            self.take()
            if self.peek() is not None and 0x13447 <= self.peek() <= 0x13455:
                closing_damage = self.take()-0x13446
        starts, ends = ((WALL_START,WALL_END) if control == WALL else
                        (PLAIN_START,PLAIN_END))
        if (opening is not None and opening not in starts or
            closing is not None and closing not in ends):
            self.fail('enclosure endpoint does not match plain/walled control family')
        if not parts: parts = [EgyptianNode('blank',size=(1,1))]
        kind = ('walled' if control == WALL else
                'rectangle' if opening in {0x13258,0x13259,0x1325A} or
                closing in {0x1325B,0x1325C,0x1325D,0x13282} else 'cartouche')
        return EgyptianNode('enclosure',tuple(parts),enclosure=kind,
                            ends=(opening is not None,closing is not None),
                            endpoint_damage=(opening_damage,closing_damage),
                            endpoint_codepoints=(opening,closing))

class EgyptianParser:
    parser_version = PARSER_VERSION

    def parse(self, text: str) -> ParsedEgyptianRun:
        reader = _Reader(text)
        parts = reader.sequence()
        if not parts: raise EgyptianParseError(text,'empty Egyptian run')
        return ParsedEgyptianRun(text,self.parser_version,EgyptianNode('run',tuple(parts)))

    def layout(self,text: str,font: FontMetrics,direction='ltr',
               writing_mode='horizontal') -> RenderResult:
        layout_options(dict(direction=direction,writing_mode=writing_mode))
        return EgyptianLayout(font,direction).layout(self.parse(text))
