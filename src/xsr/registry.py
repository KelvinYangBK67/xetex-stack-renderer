"""Generic Unicode range registry and contiguous run detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator


@dataclass(frozen=True, order=True)
class UnicodeRange:
    """An inclusive Unicode code-point range."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if not (0 <= self.start <= self.end <= 0x10FFFF):
            raise ValueError(f"invalid Unicode range: {self.start:#x}-{self.end:#x}")

    def contains(self, codepoint: int) -> bool:
        return self.start <= codepoint <= self.end


@dataclass(frozen=True)
class ScriptSpec:
    name: str
    ranges: tuple[UnicodeRange, ...]


@dataclass(frozen=True)
class DetectedRun:
    """A maximal contiguous span sharing the same registered script."""

    script: str | None
    text: str
    start: int
    end: int


class Registry:
    """Register scripts independently from renderer implementations."""

    def __init__(self) -> None:
        self._scripts: dict[str, ScriptSpec] = {}

    @property
    def scripts(self) -> tuple[ScriptSpec, ...]:
        return tuple(self._scripts.values())

    def register(self, name: str, ranges: Iterable[tuple[int, int]]) -> ScriptSpec:
        if not name or name in self._scripts:
            raise ValueError(f"script is empty or already registered: {name!r}")

        new_ranges = tuple(UnicodeRange(start, end) for start, end in ranges)
        if not new_ranges:
            raise ValueError(f"script {name!r} has no ranges")

        for existing in self._scripts.values():
            for left in new_ranges:
                for right in existing.ranges:
                    if left.start <= right.end and right.start <= left.end:
                        raise ValueError(
                            f"range overlap between {name!r} and {existing.name!r}"
                        )

        spec = ScriptSpec(name=name, ranges=new_ranges)
        self._scripts[name] = spec
        return spec

    def script_for(self, character: str) -> str | None:
        if len(character) != 1:
            raise ValueError("script_for expects exactly one Unicode character")
        codepoint = ord(character)
        for script in self._scripts.values():
            if any(item.contains(codepoint) for item in script.ranges):
                return script.name
        return None

    def detect_runs(self, text: str) -> Iterator[DetectedRun]:
        """Yield maximal runs; unregistered text has ``script=None``."""
        if not text:
            return

        start = 0
        current = self.script_for(text[0])
        for index, character in enumerate(text[1:], start=1):
            script = self.script_for(character)
            if script != current:
                yield DetectedRun(current, text[start:index], start, index)
                start = index
                current = script
        yield DetectedRun(current, text[start:], start, len(text))

    def script_runs(self, text: str) -> Iterator[DetectedRun]:
        return (run for run in self.detect_runs(text) if run.script is not None)

