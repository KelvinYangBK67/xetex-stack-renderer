import math
import pytest
from xsr.egyptian import EgyptianLayoutError, GlyphPlacement, HieropyAdapter, RenderResult, serialize_tex_layout

A, B, C = map(chr, (0x13000, 0x13050, 0x13153))
H, V, BEGIN, END = map(chr, (0x13431, 0x13430, 0x13437, 0x13438))


def assert_contained(result):
    assert result.width > 0 and result.height > 0 and result.depth == 0
    for g in result.glyphs:
        assert all(math.isfinite(v) for v in (g.x, g.y, g.width, g.height, g.scale))
        assert g.width > 0 and g.height > 0 and g.scale > 0
        assert g.x >= 0 and g.y >= 0
        assert g.x + g.width <= result.width + 1e-9
        assert g.y + g.height <= result.height + 1e-9
    for i, a in enumerate(result.glyphs):
        for b in result.glyphs[i + 1:]:
            assert (a.x + a.width <= b.x or b.x + b.width <= a.x or
                    a.y + a.height <= b.y or b.y + b.height <= a.y)


def test_single_sign_geometry(font):
    result = HieropyAdapter().layout(A, font)
    metric = font.glyph(ord(A))
    g, = result.glyphs
    assert g.width == pytest.approx(metric.width * g.scale)
    assert g.height == pytest.approx(metric.height * g.scale)
    assert g.ink_left == metric.bounds[0]
    assert g.ink_top == metric.bounds[3]
    assert g.x == pytest.approx(0.04) and g.y == pytest.approx(0.04)
    assert result.width == pytest.approx(g.width + 0.08)
    assert result.height == pytest.approx(g.height + 0.08)
    assert_contained(result)


def test_horizontal_joiner_geometry(font):
    result = HieropyAdapter().layout(A + H + B, font)
    first, second = result.glyphs
    assert [g.codepoint for g in result.glyphs] == [ord(A), ord(B)]
    assert first.x + first.width < second.x
    assert first.y + first.height / 2 == pytest.approx(second.y + second.height / 2)
    assert first.scale == pytest.approx(second.scale)
    assert_contained(result)


def test_vertical_joiner_geometry(font):
    result = HieropyAdapter().layout(A + V + B, font)
    first, second = result.glyphs
    assert [g.codepoint for g in result.glyphs] == [ord(A), ord(B)]
    assert first.y + first.height < second.y
    assert first.x + first.width / 2 == pytest.approx(second.x + second.width / 2)
    assert first.scale == pytest.approx(second.scale)
    assert 0 < first.scale < 1
    assert result.height <= 1.08 + 1e-9
    assert_contained(result)


def test_nested_horizontal_and_vertical_geometry(font):
    vertical_outer = HieropyAdapter().layout(A + H + B + V + C, font)
    h_first, h_second, bottom = vertical_outer.glyphs
    assert h_first.y + h_first.height / 2 == pytest.approx(h_second.y + h_second.height / 2)
    assert h_first.x + h_first.width < h_second.x
    assert max(g.y + g.height for g in (h_first, h_second)) < bottom.y
    assert_contained(vertical_outer)
    horizontal_outer = HieropyAdapter().layout(A + H + BEGIN + B + V + C + END, font)
    left, v_first, v_second = horizontal_outer.glyphs
    assert left.x + left.width < min(v_first.x, v_second.x)
    assert v_first.y + v_first.height < v_second.y
    assert_contained(horizontal_outer)


def test_geometry_serializes_to_xetex_layout_commands():
    result = RenderResult(1.5, 1.2, 0.0, (GlyphPlacement(0x13000, 0.1, 0.2, 0.7, 0.8, 0.75, -0.1, 0.9),))
    assert serialize_tex_layout(result) == (
        r'\xsrEgyptianLayout{1.5}{1.2}{0}{1}'
        r'{\xsrEgyptianGlyph{13000}{0.1}{0.2}{0.7}{0.8}{0.75}{-0.1}{0.9}}')


def test_overlay_centers_actual_ink(font):
    result = HieropyAdapter().layout(A + chr(0x13436) + B, font)
    first, second = result.glyphs
    assert first.x + first.width/2 == pytest.approx(second.x + second.width/2)
    assert first.y + first.height/2 == pytest.approx(second.y + second.height/2)

def test_unsupported_delimiter_damage_is_explicit(font):
    with pytest.raises(EgyptianLayoutError, match='damaged enclosure delimiters'):
        HieropyAdapter().layout(chr(0x13379)+chr(0x13447)+chr(0x1343C)+A+chr(0x1343D)+chr(0x1337A),font)


def test_hieropy_geometry_is_never_used(monkeypatch, font):
    from hieropy.unistructure import Fragment, Horizontal, Literal, Vertical
    def forbidden(*args, **kwargs):
        pytest.fail('Hieropy geometry was used')
    for cls in (Fragment, Horizontal, Literal, Vertical):
        monkeypatch.setattr(cls, 'size', forbidden)
        monkeypatch.setattr(cls, 'format', forbidden)
    assert_contained(HieropyAdapter().layout(A + H + B + V + C, font))


def test_showcase_sequences_have_contained_disjoint_ink(font):
    from pathlib import Path
    from xsr import build_default_registry
    source = (Path(__file__).resolve().parents[1] / 'examples/font-metrics-showcase.tex').read_text(encoding='utf-8')
    sequences = {run.text for run in build_default_registry().script_runs(source)}
    assert len(sequences) >= 12
    for text in sequences:
        assert_contained(HieropyAdapter().layout(text, font))
