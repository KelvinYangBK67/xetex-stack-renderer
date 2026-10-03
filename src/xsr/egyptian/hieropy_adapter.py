"""Convert Hieropy syntax to an immutable XSR tree, never calling its layout."""
from typing import Any
from ..font_metrics import FontMetrics
from .model import EgyptianNode, ParsedEgyptianRun, RenderResult
from .layout import EgyptianLayout, EgyptianLayoutError


class EgyptianParseError(ValueError):
    def __init__(self, text: str, detail: str) -> None:
        self.text = text
        self.detail = detail
        codepoints = ' '.join(f'U+{ord(character):05X}' for character in text)
        super().__init__(f'Hieropy could not parse Egyptian run [{codepoints}]: {detail}')


def _structure(node: object) -> EgyptianNode:
    from hieropy.unistructure import Fragment, Horizontal, Literal, Vertical
    if isinstance(node, Literal):
        unsupported = [label for flag, label in (
            (node.vs, 'rotation/variation'), (node.mirror, 'mirror'),
            (node.damage, 'damage')) if flag]
        if unsupported:
            raise EgyptianLayoutError('unsupported Literal feature(s): ' + ', '.join(unsupported))
        return EgyptianNode('sign', codepoint=ord(node.ch))
    kinds = {Fragment: 'run', Horizontal: 'horizontal', Vertical: 'vertical'}
    if type(node) not in kinds:
        raise EgyptianLayoutError(f'unsupported Hieropy group for basic H/V layout: {type(node).__name__}')
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
