from pathlib import Path

from xsr.cache import RenderCache
from xsr.egyptian import EgyptianBackend
from xsr.renderer import Renderer, main, read_request


def test_backend_receives_and_renders_a_complete_run(tmp_path: Path) -> None:
    renderer = Renderer(RenderCache(tmp_path / "cache"))
    renderer.register(EgyptianBackend())
    run = chr(0x13000) + chr(0x13430) + chr(0x13460)

    tex = renderer.render("egyptian", run)

    assert tex.startswith(r"\xsrBackendResult{egyptian}{3}")
    assert len(list((tmp_path / "cache").glob("*.tex"))) == 1
    assert renderer.render("egyptian", run) == tex


def test_render_request_protocol(tmp_path: Path) -> None:
    request = tmp_path / "run.req"
    response = tmp_path / "run.tex"
    request.write_text(
        "XSR1\nscript=egyptian\ncodepoints=13000 13430 13460\n",
        encoding="utf-8",
    )

    assert read_request(request) == (
        "egyptian",
        chr(0x13000) + chr(0x13430) + chr(0x13460),
    )
    assert (
        main(
            [
                "render",
                "--backend",
                "egyptian",
                "--input",
                str(request),
                "--output",
                str(response),
                "--cache-dir",
                str(tmp_path / "cache"),
            ]
        )
        == 0
    )
    assert response.read_text(encoding="utf-8").startswith(
        r"\xsrBackendResult{egyptian}{3}"
    )


def test_preprocess_writes_numbered_responses_and_manifest(tmp_path: Path) -> None:
    source = tmp_path / "sample.tex"
    run = chr(0x13000) + chr(0x13430)
    source.write_text(f"ordinary {run} ordinary\n", encoding="utf-8")
    output = tmp_path / "prepared"

    assert (
        main(
            [
                "preprocess",
                "--input",
                str(source),
                "--output-dir",
                str(output),
            ]
        )
        == 0
    )

    response = output / "sample.xsr-1.tex"
    manifest = output / "sample.xsr-manifest.json"
    assert response.read_text(encoding="utf-8").startswith(
        r"\xsrBackendResult{egyptian}{2}"
    )
    assert '"script": "egyptian"' in manifest.read_text(encoding="utf-8")

