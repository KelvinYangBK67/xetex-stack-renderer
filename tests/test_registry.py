from xsr import build_default_registry


def test_egyptian_range_boundaries_are_registered() -> None:
    registry = build_default_registry()

    for codepoint in (0x13000, 0x1342F, 0x13430, 0x1345F, 0x13460, 0x143FF):
        assert registry.script_for(chr(codepoint)) == "egyptian"

    for codepoint in (0x12FFF, 0x14400):
        assert registry.script_for(chr(codepoint)) is None


def test_detection_yields_one_complete_script_run() -> None:
    registry = build_default_registry()
    text = "before " + chr(0x13000) + chr(0x13430) + chr(0x13460) + " after"

    runs = list(registry.detect_runs(text))

    assert [(run.script, run.text) for run in runs] == [
        (None, "before "),
        ("egyptian", chr(0x13000) + chr(0x13430) + chr(0x13460)),
        (None, " after"),
    ]

