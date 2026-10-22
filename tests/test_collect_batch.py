"""The XSR 1.5 TeX collect/batch protocol works with shell escape disabled."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from fixtures.inline_assets import make_asset
from xsr.renderer import main, read_request_collection

ROOT = Path(__file__).resolve().parents[1]


def test_request_collection_rejects_partial_stream(tmp_path):
    request = tmp_path / "main.xsr-requests.req"
    request.write_text("XSR2\ndigest=AA\n", encoding="utf-8")
    with pytest.raises(ValueError, match="truncated"):
        read_request_collection(request)


@pytest.mark.skipif(shutil.which("xelatex") is None, reason="XeLaTeX unavailable")
def test_collect_batch_and_final_without_shell(tmp_path):
    asset = make_asset(tmp_path / "字形.png")
    source = tmp_path / "main.tex"
    source.write_text(
        r"\documentclass{article}"
        r"\usepackage{xetex-stack-renderer}"
        r"\GlyphRegister{one}{字形.png}"
        r"\begin{document}"
        r"A \Glyph{one} and \Glyph[scale=1.2]{one}."
        r"\end{document}",
        encoding="utf-8",
    )
    collect_dir = tmp_path / "collect"
    collect_dir.mkdir()
    env = dict(os.environ)
    env["TEXINPUTS"] = str(ROOT / "tex") + os.pathsep + env.get("TEXINPUTS", "")

    def compile(mode, out):
        result = subprocess.run(
            ["xelatex", "-no-shell-escape", "-interaction=nonstopmode",
             "-halt-on-error", "-jobname=main", "-output-directory=" + str(out),
             r"\def\XSRBuildModeOverride{" + mode + r"}\input{main.tex}"],
            cwd=tmp_path, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=90,
        )
        assert result.returncode == 0, result.stdout
        return result.stdout

    compile("collect", collect_dir)
    requests = collect_dir / "main.xsr-requests.req"
    assert len(read_request_collection(requests)) == 2
    assert main(["batch", "--input", str(requests), "--output-dir",
                 str(tmp_path), "--jobname", "main"]) == 0
    bundle = tmp_path / ".xsr/main.responses.tex"
    assert bundle.read_text(encoding="utf-8").count(r"\xsrDeclareResponse") == 1
    output = compile("preprocess", tmp_path)
    assert "XSR-BACKEND script=asset" in output
    assert (tmp_path / "main.pdf").exists()
    old = bundle.read_bytes()

    make_asset(asset, 120, 240)
    compile("collect", collect_dir)
    assert main(["batch", "--input", str(requests), "--output-dir",
                 str(tmp_path), "--jobname", "main"]) == 0
    assert bundle.read_bytes() != old
    compile("preprocess", tmp_path)
