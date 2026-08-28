import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("xelatex") is None, reason="xelatex is unavailable")
def test_xelatex_dispatches_unicode_run_to_python(tmp_path: Path) -> None:
    source = tmp_path / "integration.tex"
    source.write_text(
        "\\errorcontextlines=999\n"
        "\\documentclass{article}\n"
        "\\usepackage{xetex-stack-renderer}\n"
        "\\begin{document}\n"
        f"ordinary {chr(0x13000)}{chr(0x13430)}{chr(0x13460)} ordinary\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["TEXINPUTS"] = str(ROOT / "tex") + os.pathsep + env.get("TEXINPUTS", "")
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

    completed = subprocess.run(
        [
            "xelatex",
            "-shell-escape",
            "-interaction=nonstopmode",
            "-halt-on-error",
            source.name,
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout
    assert "XSR-DISPATCH script=egyptian codepoints=3" in completed.stdout
    assert "XSR-BACKEND script=egyptian codepoints=3" in completed.stdout
    assert (tmp_path / "integration.pdf").is_file()
