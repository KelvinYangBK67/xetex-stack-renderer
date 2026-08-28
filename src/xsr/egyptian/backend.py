"""Placeholder Egyptian backend; no EHFC layout is implemented yet."""

from __future__ import annotations

import hashlib
from typing import Mapping


class EgyptianBackend:
    name = "egyptian"
    version = "stub-1"

    def render(self, text: str, options: Mapping[str, object]) -> str:
        """Return observable TeX proving that one complete run was dispatched."""
        del options
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        return f"\\xsrBackendResult{{{self.name}}}{{{len(text)}}}{{{digest}}}\n"

