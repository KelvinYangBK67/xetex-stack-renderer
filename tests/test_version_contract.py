"""Software version is single-sourced; backend/cache protocol IDs stay independent."""
from importlib import metadata
from pathlib import Path
import warnings

import xsr
from xsr.errors import XSRError
from xsr.synthetic import XSRWarning, warn

ROOT = Path(__file__).resolve().parents[1]


def test_single_source_version_and_generated_tex_stamp():
    expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert expected == xsr.__version__ == metadata.version("xetex-stack-renderer")
    stamp = (ROOT / "tex" / "xsr-version.tex").read_text(encoding="utf-8")
    assert r"\def\xsrPackageVersion{" + expected + "}" in stamp
    for style in (ROOT / "tex").glob("*.sty"):
        content = style.read_text(encoding="utf-8")
        assert r"\input{xsr-version.tex}" in content, style
        assert r"{\xsrPackageVersion}" in content, style


def test_warning_code_is_emitted_only_once():
    error = XSRError("XSR-GLYPH-MISSING", "sample glyph missing")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warn(error.code, str(error))
    assert len(caught) == 1
    assert isinstance(caught[0].message, XSRWarning)
    assert str(caught[0].message) == "[XSR-GLYPH-MISSING] sample glyph missing"
