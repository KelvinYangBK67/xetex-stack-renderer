'''Egyptian backend with Hieropy parsing and placeholder TeX output.'''

from __future__ import annotations

import hashlib
from typing import Mapping

from .hieropy_adapter import HieropyAdapter


BACKEND_VERSION = 'hieropy-0.1.4-parse-stub-1'


class EgyptianBackend:
    name = 'egyptian'
    version = BACKEND_VERSION

    def __init__(self, adapter: HieropyAdapter | None = None) -> None:
        self.adapter = adapter or HieropyAdapter()

    def render(self, text: str, options: Mapping[str, object]) -> str:
        '''Parse one complete run before emitting the observable TeX stub.'''
        del options
        parsed = self.adapter.parse(text)
        digest = hashlib.sha256(parsed.text.encode('utf-8')).hexdigest()[:12]
        parser = f'hieropy-{parsed.parser_version}'
        return (
            f'\\xsrBackendResult{{{self.name}}}{{{len(parsed.text)}}}'
            f'{{{digest}}}{{{self.version}}}{{{parser}}}\n'
        )
