"""Convert Hieropy syntax to an immutable XSR tree, never calling its layout."""
import re
from typing import Any
from .semantics import rotation, validate_mirror, layout_options
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


def _structure(node: object, brackets=None) -> EgyptianNode:
    def convert(child):
        return _structure(child, brackets)
    from hieropy.unistructure import (
        Fragment, Horizontal, Literal, Vertical, Basic, Overlay, Enclosure,
        Singleton, Blank, Lost, BracketOpen, BracketClose,
    )
    if isinstance(node, (BracketOpen, BracketClose)):
        chars=next(brackets) if brackets is not None else node.ch
        nodes=tuple(EgyptianNode('bracket',codepoint=ord(ch)) for ch in chars)
        return nodes[0] if len(nodes)==1 else EgyptianNode('horizontal',nodes)
    if isinstance(node, (Literal, Singleton)):
        validate_mirror(ord(node.ch), getattr(node, 'mirror', False))
        return EgyptianNode('sign', codepoint=ord(node.ch),
                            rotation=rotation(ord(node.ch), getattr(node, 'vs', 0)),
                            mirror=getattr(node, 'mirror', False), damage=node.damage)
    if isinstance(node, Basic):
        # Ignore Hieropy's alternate NewGardiner glyph/slot metadata entirely.
        return EgyptianNode('insertion', (convert(node.core),) +
                            tuple(convert(n) for n in node.insertions.values()),
                            slots=tuple(node.insertions))
    if isinstance(node, Overlay):
        return EgyptianNode('overlay', (
            EgyptianNode('horizontal', tuple(convert(n) for n in node.lits1)),
            EgyptianNode('vertical', tuple(convert(n) for n in node.lits2))))
    if isinstance(node, Enclosure):
        opening = ord(node.delim_open) if node.delim_open else None
        closing = ord(node.delim_close) if node.delim_close else None
        if node.typ == 'walled':
            starts, ends = {None,0x13286,0x13288}, {None,0x13287,0x13289}
            kind = 'walled'
        else:
            starts = {None,0x13258,0x13259,0x1325A,0x13379,0x1342F}
            ends = {None,0x1325B,0x1325C,0x1325D,0x13282,0x1337A,0x1337B}
            kind = 'rectangle' if opening in {0x13258,0x13259,0x1325A} or closing in {0x1325B,0x1325C,0x1325D,0x13282} else 'cartouche'
        if opening not in starts or closing not in ends:
            raise EgyptianLayoutError('enclosure endpoint does not match plain/walled control family')
        content=tuple(convert(n) for n in node.groups) or (EgyptianNode('blank',size=(1,1)),)
        return EgyptianNode('enclosure', content,
                            enclosure=kind, ends=(opening is not None, closing is not None),
                            endpoint_damage=(node.damage_open,node.damage_close),
                            endpoint_codepoints=(opening,closing))
    if isinstance(node, Blank):
        return EgyptianNode('blank', size=(node.dim,node.dim))
    if isinstance(node, Lost):
        return EgyptianNode('lost', size=(node.width,node.height), continuous=bool(node.expand))
    kinds = {Fragment:'run', Horizontal:'horizontal', Vertical:'vertical'}
    if type(node) not in kinds:
        raise EgyptianLayoutError(f'unsupported EHFC structure: {type(node).__name__}')
    if not node.groups:
        raise EgyptianLayoutError('empty Egyptian groups cannot be laid out')
    return EgyptianNode(kinds[type(node)], tuple(convert(child) for child in node.groups))


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
        for index,ch in enumerate(text):
            if 0xFE07 <= ord(ch) <= 0xFE0F:
                raise XSRError('XSR-VARIANT-UNREGISTERED', f'U+{ord(ch):04X} has no registered Egyptian variant')
            if 0xFE00 <= ord(ch) <= 0xFE0F and index and 0x13443 <= ord(text[index-1]) <= 0x13446 and ord(ch)!=0xFE00:
                raise XSRError('XSR-VARIANT-UNREGISTERED', 'lost signs only support FE00 continuous shading')
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
            bracket_runs=[]
            def collect_brackets(match):
                bracket_runs.append(match.group())
                return match.group()[0]
            normalized=re.sub(r'[\[{\u27E8\u27E6\u2E22]+|[\]}\u27E9\u27E7\u2E23]+', collect_brackets, text)
            while True:
                reduced=re.sub('[\U00013437]([\U00013000-\U0001342F\U00013460-\U000143FF][\uFE00-\uFE06]?[\U00013440]?[\U00013447-\U00013455]?)[\U00013438]', r'\1', normalized)
                if reduced==normalized:
                    break
                normalized=reduced
            fragment = self._parser.parse(normalized)
        except Exception as error:
            raise EgyptianParseError(text, str(error) or type(error).__name__) from error
        detail = str(getattr(self._parser, 'last_error', '') or '').strip()
        if fragment is None or detail:
            raise EgyptianParseError(text, detail or 'parser returned no Fragment')
        return ParsedEgyptianRun(text, self.parser_version, _structure(fragment,iter(bracket_runs)))

    def layout(self, text: str, font: FontMetrics, direction='ltr', writing_mode='horizontal') -> RenderResult:
        layout_options(dict(direction=direction,writing_mode=writing_mode))
        return EgyptianLayout(font,direction).layout(self.parse(text))
