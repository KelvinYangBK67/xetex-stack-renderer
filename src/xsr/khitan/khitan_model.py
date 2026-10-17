"""Simple structural model; geometry and font details are separate."""
from dataclasses import dataclass


@dataclass(frozen=True)
class KhitanCluster:
    kind: str
    characters: tuple[int, ...]


@dataclass(frozen=True)
class ParsedKhitanRun:
    clusters: tuple[KhitanCluster, ...]
    separators: tuple[str, ...]


@dataclass(frozen=True)
class KhitanPlacement:
    codepoint: int
    x: float
    y: float
    width: float
    height: float
    ink_left: float
    ink_top: float
    scale: float = 1.0


@dataclass(frozen=True)
class KhitanRenderResult:
    width: float
    height: float
    depth: float
    glyphs: tuple[KhitanPlacement, ...]