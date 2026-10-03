"""Convert Hieropy syntax to an immutable XSR tree, never calling its layout."""
from typing import Any
from ..errors import XSRError
from ..font_metrics import FontMetrics
from .model import EgyptianNode, ParsedEgyptianRun, RenderResult
from .layout import EgyptianLayout, EgyptianLayoutError


class EgyptianParseError(XSRError):
    def __init__(self, text: str, detail: str) -> None:
        self.text = text
        self.detail = detail
        codepoints = ' '.join(f'U+{ord(character):05X}' for character in text)
        super().__init__('XSR-PARSE', f'Hieropy could not parse Egyptian run [{codepoints}]: {detail}')


def _structure(node: object) -> EgyptianNode:
    from hieropy.unistructure import (
        Fragment, Horizontal, Literal, Vertical, Basic, Overlay, Enclosure,
        Singleton, Blank, Lost,
    )
    if isinstance(node, (Literal, Singleton)):
        return EgyptianNode('sign', codepoint=ord(node.ch),
                            rotation=(0,90,180,270,45,135,225,315)[getattr(node, 'vs', 0)],
                            mirror=getattr(node, 'mirror', False), damage=node.damage)
    if isinstance(node, Basic):
        # Ignore Hieropy's alternate NewGardiner glyph/slot metadata entirely.
        return EgyptianNode('insertion', (_structure(node.core),) +
                            tuple(_structure(n) for n in node.insertions.values()),
                            slots=tuple(node.insertions))
    if isinstance(node, Overlay):
        return EgyptianNode('overlay', (
            EgyptianNode('horizontal', tuple(_structure(n) for n in node.lits1)),
            EgyptianNode('vertical', tuple(_structure(n) for n in node.lits2))))
    if isinstance(node, Enclosure):
        if node.damage_open or node.damage_close:
            raise EgyptianLayoutError('damaged enclosure delimiters are not supported')
        opening = ord(node.delim_open) if node.delim_open else None
        closing = ord(node.delim_close) if node.delim_close else None
        families = {
            'cartouche': ({None, 0x13379}, {None, 0x1337A}),
            'rectangle': ({None, 0x13258}, {None, 0x1325B}),
            'walled': ({None, 0x13286}, {None, 0x13287}),
        }
        kind = 'walled' if node.typ == 'walled' else 'cartouche'
        if opening == 0x13258 or closing == 0x1325B:
            kind = 'rectangle'
        starts, ends = families[kind]
        if opening not in starts or closing not in ends:
            cps = ' '.join(f'U+{c:05X}' for c in (opening,closing) if c)
            raise EgyptianLayoutError(f'unsupported enclosure delimiter combination {cps}')
        if not node.groups:
            raise EgyptianLayoutError('empty enclosures are not supported')
        return EgyptianNode('enclosure', tuple(_structure(n) for n in node.groups),
                            enclosure=kind, ends=(opening is not None, closing is not None))
    if isinstance(node, Blank):
        return EgyptianNode('blank', size=(node.dim,node.dim))
    if isinstance(node, Lost):
        if node.expand:
            raise EgyptianLayoutError('continuous lost-sign shading (lost sign + variation selector) is not supported')
        return EgyptianNode('lost', size=(node.width,node.height))
    kinds = {Fragment:'run', Horizontal:'horizontal', Vertical:'vertical'}
    if type(node) not in kinds:
        raise EgyptianLayoutError(f'unsupported EHFC structure: {type(node).__name__}')
    if not node.groups:
        raise EgyptianLayoutError('empty Egyptian groups cannot be laid out')
    return EgyptianNode(kinds[type(node)], tuple(_structure(child) for child in node.groups))


class HieropyAdapter:
    def __init__(self, parser: Any | None = None) -> None:
        if parser is None:
            import hieropy
            parser = hieropy.UniParser()
            self.parser_version = hieropy.__version__
        else:
            self.parser_version = getattr(parser, 'version', 'unknown')
        self._parser = parser

    def parse(self, text: str) -> ParsedEgyptianRun:
        # Hieropy does not check that enclosure opening/closing types match.
        stack = []
        for ch in text:
            if ord(ch) in (0x1343C, 0x1343E):
                stack.append(ord(ch)+1)
            elif ord(ch) in (0x1343D, 0x1343F):
                if not stack or stack.pop() != ord(ch):
                    raise EgyptianParseError(text, 'mismatched enclosure controls')
        if stack:
            raise EgyptianParseError(text, 'unclosed enclosure control')
        try:
            fragment = self._parser.parse(text)
        except Exception as error:
            raise EgyptianParseError(text, str(error) or type(error).__name__) from error
        detail = str(getattr(self._parser, 'last_error', '') or '').strip()
        if fragment is None or detail:
            raise EgyptianParseError(text, detail or 'parser returned no Fragment')
        return ParsedEgyptianRun(text, self.parser_version, _structure(fragment))

    def layout(self, text: str, font: FontMetrics) -> RenderResult:
        return EgyptianLayout(font).layout(self.parse(text))
