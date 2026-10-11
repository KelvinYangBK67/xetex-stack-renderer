"""Round-trip Unicode source through atomic PDF ActualText."""
import shutil
import subprocess

import pytest

from xsr.copy_text import actual_text_hex, attach_actual_text
from xsr.egyptian import EgyptianParser

EG_A, EG_B = chr(0x13000), chr(0x13153)
EHFC_H, EHFC_V = chr(0x13431), chr(0x13430)
K_A, K_B, K_C = (chr(cp) for cp in (0x18B01, 0x18B02, 0x18B03))
KHSF, ZWSP = chr(0x16FE4), chr(0x200B)


def test_utf16be_preserves_supplementary_and_control_characters():
    source = EG_A + EHFC_H + EG_B + KHSF + ZWSP + chr(0xE0100)
    encoded = actual_text_hex(source)
    assert bytes.fromhex(encoded).decode("utf-16-be") == source
    assert "D80C" in encoded
    assert "DB40" in encoded


def test_egyptian_quadrat_spans_follow_source_order():
    source = EG_A + EHFC_H + EG_B + EG_A + EHFC_V + EG_B
    parsed = EgyptianParser().parse(source)
    assert parsed.quadrat_texts == (EG_A + EHFC_H + EG_B, EG_A + EHFC_V + EG_B)
    assert "".join(parsed.quadrat_texts) == source


def test_atomic_markup_encodes_original_sequence():
    source = K_A + KHSF + K_B
    marked = attach_actual_text(source, r"\xsrKhitanLayout{1}{1}{0}{2}{}")
    assert marked.startswith(r"\xsrActualText{")
    assert bytes.fromhex(marked.split("{", 2)[1].split("}", 1)[0]).decode("utf-16-be") == source


@pytest.mark.skipif(shutil.which("xelatex") is None or shutil.which("pdftotext") is None,
                    reason="XeLaTeX and Poppler required")
def test_ehfc_pdf_extraction(tmp_path):
    from test_tex_integration import run_xelatex
    source = EG_A + EHFC_H + EG_B + EG_A
    result = run_xelatex(tmp_path, "Before " + source + " after")
    assert result.returncode == 0, result.stdout
    actual = subprocess.check_output(
        ["pdftotext", "-raw", str(tmp_path / "integration.pdf"), "-"],
        encoding="utf-8",
    )
    # The PDF reader may infer whitespace between adjacent quadrats from
    # visual spacing; each atomic quadrat nevertheless retains its EHFC text.
    assert actual.count(EG_A + EHFC_H + EG_B) == 1, repr(actual)
    assert actual.count(EG_A) == 2, repr(actual)


@pytest.mark.skipif(shutil.which("xelatex") is None or shutil.which("pdftotext") is None,
                    reason="XeLaTeX and Poppler required")
def test_khsf_and_zwsp_pdf_extraction(tmp_path):
    from test_khitan_tex import AVAILABLE, compile_tex
    if not AVAILABLE:
        pytest.skip("Khitan font unavailable")
    source = K_A + KHSF + K_B + ZWSP + K_A + K_C
    _stdout, pdf = compile_tex(tmp_path, "Before " + source + " after")
    actual = subprocess.check_output(["pdftotext", "-raw", str(pdf), "-"],
                                     encoding="utf-8")
    assert actual.count(source) == 1, repr(actual)
