"""Small content-addressed cache used by external renderers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Mapping


class RenderCache:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    @staticmethod
    def key(
        backend: str,
        backend_version: str,
        text: str,
        options: Mapping[str, object] | None = None,
    ) -> str:
        payload = {
            "backend": backend,
            "backend_version": backend_version,
            "options": dict(options or {}),
            "text": text,
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def get(self, key: str) -> str | None:
        path = self.directory / f"{key}.tex"
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    def put(self, key: str, tex: str) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / f"{key}.tex"
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{key}.", suffix=".tmp", dir=self.directory
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(tex)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

