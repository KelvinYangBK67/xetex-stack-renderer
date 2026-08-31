'''Narrow adapter from Unicode Egyptian/EHFC text to Hieropy.'''

from __future__ import annotations

from typing import Any

from .model import ParsedEgyptianRun


class EgyptianParseError(ValueError):
    '''Raised when Hieropy rejects an Egyptian Unicode/EHFC run.'''

    def __init__(self, text: str, detail: str) -> None:
        self.text = text
        self.detail = detail
        codepoints = ' '.join(f'U+{ord(character):05X}' for character in text)
        super().__init__(f'Hieropy could not parse Egyptian run [{codepoints}]: {detail}')


class HieropyAdapter:
    '''Keep Hieropy classes and error conventions behind one XSR API.'''

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
            detail = str(error) or type(error).__name__
            raise EgyptianParseError(text, detail) from error

        detail = str(getattr(self._parser, 'last_error', '') or '').strip()
        if fragment is None or detail:
            raise EgyptianParseError(text, detail or 'parser returned no Fragment')

        return ParsedEgyptianRun(
            text=text,
            parser_version=self.parser_version,
            fragment=fragment,
        )
