'''Minimal XSR-owned result at the Hieropy boundary.'''

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedEgyptianRun:
    '''A parsed run with Hieropy's Fragment kept deliberately opaque.'''

    text: str
    parser_version: str
    fragment: object = field(repr=False, compare=False)
