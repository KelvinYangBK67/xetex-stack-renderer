"""Original Unicode extraction from XSR's atomic PDF layout units."""

def actual_text_hex(text: str) -> str:
    """Encode a source unit as PDF UTF-16BE (without the BOM)."""
    if not text:
        raise ValueError("ActualText unit must not be empty")
    return text.encode("utf-16-be").hex().upper()


def attach_actual_text(text: str, drawn_tex: str) -> str:
    """Bind drawn TeX to literal source text; never infer from glyph order."""
    return r"\xsrActualText{" + actual_text_hex(text) + "}{" + drawn_tex + "}"
