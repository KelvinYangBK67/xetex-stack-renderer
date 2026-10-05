"""Parser-only EHFC regression corpus, including every showcase run."""
from pathlib import Path
import pytest
from xsr import build_default_registry
from xsr.egyptian import EgyptianParser
from xsr.egyptian.source import source_runs

ROOT = Path(__file__).resolve().parents[1]
SHOWCASE = ROOT / 'examples/egyptian-showcase.tex'
SHOWCASE_TEXT = SHOWCASE.read_text(encoding='utf-8')
RUNS = tuple(sorted({run.text for run in source_runs(SHOWCASE_TEXT, build_default_registry())}))

def chars(*cps):
    return ''.join(map(chr,cps))

CORPUS = (
    (chars(0x13000,0x13431,0x13050,0x13430,0x13153),'vertical'),
    (chars(0x13437,0x13000,0x13430,0x13050,0x13438,0x13431,0x13153),'horizontal'),
    (chars(0x13102,0x13432,0x13437,0x13093,0x1343A,0x1340D,0x13438),'insertion'),
    (chars(0x13102,0x13432,0x13437,0x133CF,0x13430,0x133CF,0x13438),'insertion'),
    (chars(0x13193,0x13433,0x13000,0x13431,0x13153),'horizontal'),
    (chars(0x13379,0x13447,0x1343C,0x13000,0x13431,0x13153,0x1343D,0x1337A,0x13455),'enclosure'),
    (chars(0x13288,0x1343E,0x13153,0x1343F,0x13289),'enclosure'),
    (chars(0x1343C,0x13000,0x1343E,0x13050,0x1343F,0x1343D),'enclosure'),
    (chars(0x1343C,0x1343D),'enclosure'),
    (chars(0x13012,0xFE03,0x13440,0x13455),'sign'),
    (chars(0x13443,0xFE00,0x13431,0x13443,0xFE00),'horizontal'),
    ('[['+chars(0x13000)+']]','horizontal'),
    ('['+chars(0x1308B,0x13430,0x133CF,0x13431)+'['+chars(0x133E5),'vertical'),
)

def descendants(node):
    yield node
    for child in node.children:
        yield from descendants(child)

@pytest.mark.parametrize('run',RUNS,ids=lambda s: '-'.join(f'{ord(c):X}' for c in s[:4]))
def test_every_showcase_run_has_native_tree(run):
    parsed = EgyptianParser().parse(run)
    assert parsed.text == run
    assert parsed.parser_version == '0.7'
    assert parsed.structure.kind == 'run'
    assert parsed.structure.children
    assert all(node.kind in {'run','sign','horizontal','vertical','insertion',
        'overlay','enclosure','blank','lost','bracket'} for node in descendants(parsed.structure))

@pytest.mark.parametrize('run,kind',CORPUS)
def test_regression_expression_root_kind(run,kind):
    parsed = EgyptianParser().parse(run)
    assert parsed.structure.children[0].kind == kind
