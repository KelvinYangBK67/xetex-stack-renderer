"""Fixed KSS stack slots with unscaled, ink-centred selected-font glyphs."""
from ..synthetic import FallbackFont
from .model import KhitanCluster, KhitanPlacement, KhitanRenderResult


def slots(cluster: KhitanCluster) -> tuple[tuple[int, int], ...]:
    """Return (row, doubled-column): 0 left, 1 middle, 2 right."""
    n = len(cluster.characters)
    result = []
    offset = 0
    if cluster.kind == 'B':
        result.append((0, 1))
        offset = 1
    for i in range(offset, n):
        row = (i - offset) // 2 + (1 if offset else 0)
        result.append((row, 0 if (i - offset) % 2 == 0 else 2))
    if (n - offset) % 2:
        row, _ = result[-1]
        result[-1] = (row, 1)
    return tuple(result)


class KhitanLayout:
    def __init__(self, font):
        self.font = font if isinstance(font, FallbackFont) else FallbackFont(font)

    def cluster(self, cluster: KhitanCluster) -> KhitanRenderResult:
        metrics = [self.font.glyph(cp) for cp in cluster.characters]
        cell_width = max(1.0, *(max(m.advance, m.width) for m in metrics))
        cell_height = max(1.0, *(m.height for m in metrics))
        positions = slots(cluster)
        two_columns = any(column != 1 for _, column in positions)
        width = cell_width * (2 if two_columns else 1)
        glyphs = []
        for cp, metric, (row, column) in zip(cluster.characters, metrics, positions):
            center = (column + 1) * cell_width / 2 if two_columns else cell_width / 2
            left = center - metric.width / 2
            top = row * cell_height + (cell_height - metric.height) / 2
            glyphs.append(KhitanPlacement(cp, left, top, metric.width, metric.height,
                                          metric.bounds[0], metric.bounds[3]))
        height = (max(row for row, _ in positions) + 1) * cell_height
        return KhitanRenderResult(width, height, 0.0, tuple(glyphs))
