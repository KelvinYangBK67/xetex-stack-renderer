import pytest

from xsr.egyptian import EgyptianParseError, EgyptianParser, ParsedEgyptianRun


def test_valid_ehfc_is_parsed_natively() -> None:
    text = chr(0x13000) + chr(0x13431) + chr(0x13050)

    parsed = EgyptianParser().parse(text)

    assert isinstance(parsed, ParsedEgyptianRun)
    assert parsed.text == text
    assert parsed.parser_version == '0.7'
    assert parsed.structure.kind == 'run'
    assert parsed.structure.children[0].kind == 'horizontal'
    assert [n.codepoint for n in parsed.structure.children[0].children] == [0x13000, 0x13050]


def test_invalid_ehfc_raises_xsr_parse_error() -> None:
    text = chr(0x13000) + chr(0x13431)

    with pytest.raises(EgyptianParseError) as caught:
        EgyptianParser().parse(text)

    message = str(caught.value)
    assert 'Unexpected end of input' in message
    assert 'U+13000 U+13431' in message
