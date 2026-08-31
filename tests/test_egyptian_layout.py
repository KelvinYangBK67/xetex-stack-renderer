import pytest

from xsr.egyptian import (
    EgyptianLayoutError,
    GlyphPlacement,
    HieropyAdapter,
    RenderResult,
    serialize_tex_layout,
)


A = chr(0x13000)
B = chr(0x13050)
C = chr(0x13153)
H = chr(0x13431)
V = chr(0x13430)
BEGIN = chr(0x13437)
END = chr(0x13438)


def test_single_sign_geometry() -> None:
    result = HieropyAdapter().layout(A)

    assert result.width == pytest.approx(0.86)
    assert result.height == pytest.approx(1.16)
    assert result.depth == 0
    assert result.glyphs == (
        GlyphPlacement(
            codepoint=0x13000,
            x=pytest.approx(0.08),
            y=pytest.approx(0.08),
            width=pytest.approx(0.7),
            height=pytest.approx(1.0),
            scale=pytest.approx(1.0),
        ),
    )


def test_horizontal_joiner_geometry() -> None:
    result = HieropyAdapter().layout(A + H + B)
    first, second = result.glyphs

    assert [glyph.codepoint for glyph in result.glyphs] == [0x13000, 0x13050]
    assert first.x + first.width < second.x
    assert first.y == pytest.approx(second.y)
    assert first.scale == pytest.approx(1.0)
    assert second.scale == pytest.approx(1.0)


def test_vertical_joiner_geometry() -> None:
    result = HieropyAdapter().layout(A + V + B)
    first, second = result.glyphs

    assert [glyph.codepoint for glyph in result.glyphs] == [0x13000, 0x13050]
    assert first.y + first.height < second.y
    assert first.scale == pytest.approx(second.scale)
    assert 0 < first.scale < 1
    assert result.height == pytest.approx(1.16)


def test_nested_horizontal_and_vertical_geometry() -> None:
    vertical_outer = HieropyAdapter().layout(A + H + B + V + C)
    h_first, h_second, bottom = vertical_outer.glyphs
    assert h_first.y == pytest.approx(h_second.y)
    assert h_first.x < h_second.x
    assert h_first.y + h_first.height < bottom.y

    horizontal_outer = HieropyAdapter().layout(
        A + H + BEGIN + B + V + C + END
    )
    left, v_first, v_second = horizontal_outer.glyphs
    assert left.x + left.width < v_first.x
    assert v_first.y + v_first.height < v_second.y


def test_geometry_serializes_to_xetex_layout_commands() -> None:
    result = RenderResult(
        width=1.5,
        height=1.2,
        depth=0.0,
        glyphs=(
            GlyphPlacement(
                codepoint=0x13000,
                x=0.1,
                y=0.2,
                width=0.7,
                height=0.8,
                scale=0.75,
            ),
        ),
    )

    assert serialize_tex_layout(result) == (
        r'\xsrEgyptianLayout{1.5}{1.2}{0}{1}'
        r'{\xsrEgyptianGlyph{13000}{0.1}{0.2}{0.7}{0.8}{0.75}}'
    )


def test_unsupported_overlay_is_not_silently_rendered() -> None:
    with pytest.raises(EgyptianLayoutError, match='Overlay'):
        HieropyAdapter().layout(A + chr(0x13436) + B)
