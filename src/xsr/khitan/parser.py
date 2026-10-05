"""Unicode 18 Khitan cluster grammar. No font-specific shaping."""
from ..errors import XSRError
from .model import KhitanCluster, ParsedKhitanRun

FILLER = 0x16FE4
SEPARATORS = {0x20: 'space', 0x200B: 'zwsp'}


def is_khitan(codepoint: int) -> bool:
    return 0x18B00 <= codepoint <= 0x18CDA or codepoint == 0x18CFF


class KhitanParser:
    parser_version = '0.8'

    def parse(self, text: str) -> ParsedKhitanRun:
        if not text:
            raise XSRError('XSR-KHITAN-EMPTY', 'empty Khitan run')
        clusters: list[KhitanCluster] = []
        separators: list[str] = []
        chars: list[int] = []
        kind = 'A'
        for index, character in enumerate(text):
            cp = ord(character)
            if cp in SEPARATORS:
                if not chars:
                    raise XSRError('XSR-KHITAN-EMPTY', f'empty cluster at offset {index}')
                clusters.append(KhitanCluster(kind, tuple(chars)))
                separators.append(SEPARATORS[cp])
                chars = []
                kind = 'A'
            elif cp == FILLER:
                if len(chars) != 1 or kind == 'B':
                    raise XSRError('XSR-KHITAN-FILLER', f'filler must occur once after the first KSS sign at offset {index}')
                if index + 1 == len(text) or not is_khitan(ord(text[index + 1])):
                    raise XSRError('XSR-KHITAN-FILLER', f'filler requires a following KSS sign at offset {index}')
                kind = 'B'
            elif is_khitan(cp):
                chars.append(cp)
            else:
                raise XSRError('XSR-KHITAN-CONTROL', f'unsupported character U+{cp:04X} at offset {index}')
        if not chars:
            raise XSRError('XSR-KHITAN-EMPTY', 'run ends after a separator')
        clusters.append(KhitanCluster(kind, tuple(chars)))
        return ParsedKhitanRun(tuple(clusters), tuple(separators))