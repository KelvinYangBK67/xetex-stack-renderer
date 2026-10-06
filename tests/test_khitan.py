"""Khitan syntax and fixed-slot geometry, independent of OpenType shaping."""
from pathlib import Path
import os
import json
import pytest

from xsr import build_default_registry
from xsr.errors import XSRError
from xsr.font_metrics import GlyphMetrics, load_font
from xsr.khitan import KhitanParser, KhitanLayout
from xsr.khitan.layout import slots
from xsr.khitan.model import KhitanCluster

A = chr(0x18B01)
B = chr(0x18B02)
F = chr(0x16FE4)
Z = chr(0x200B)
I = chr(0x18B00)
M = chr(0x18CFF)


@pytest.mark.parametrize(('text', 'kind', 'chars'), [
    (A, 'A', (0x18B01,)),
    (A+B, 'A', (0x18B01, 0x18B02)),
    (A+B+A, 'A', (0x18B01, 0x18B02, 0x18B01)),
    (A*4, 'A', (0x18B01,)*4),
    (A*8, 'A', (0x18B01,)*8),
    (A+F+B, 'B', (0x18B01, 0x18B02)),
    (A+F+B+A, 'B', (0x18B01, 0x18B02, 0x18B01)),
    (A+F+B*7, 'B', (0x18B01,)+(0x18B02,)*7),
    (I+A, 'A', (0x18B00, 0x18B01)),
    (A+M, 'A', (0x18B01, 0x18CFF)),
])
def test_structural_clusters(text, kind, chars):
    parsed = KhitanParser().parse(text)
    assert parsed.clusters == (KhitanCluster(kind, chars),)
    assert parsed.separators == ()


@pytest.mark.parametrize(('separator', 'name'), [
    (' ', 'space'), (Z, 'zwsp'),
])
def test_separator_preserved(separator, name):
    parsed = KhitanParser().parse(A+B+separator+A+F+B)
    assert parsed.clusters == (KhitanCluster('A', (0x18B01, 0x18B02)),
                               KhitanCluster('B', (0x18B01, 0x18B02)))
    assert parsed.separators == (name,)


def test_mixed_separators():
    parsed = KhitanParser().parse(A+' '+B+Z+A)
    assert parsed.separators == ('space', 'zwsp')
    assert len(parsed.clusters) == 3


@pytest.mark.parametrize('text', [
    '', F, F+A, A+F, A+F+F+B, A+B+F+A, A+F+' '+B,
    ' '+A, A+' ', A+'  '+B, A+Z+Z+B, A+chr(0x18CDB),
    A+'!', 'Latin'+A,
])
def test_invalid_run(text):
    with pytest.raises(XSRError):
        KhitanParser().parse(text)


def test_host_dispatch_keeps_neighbors_and_cluster_space():
    registry = build_default_registry()
    runs = tuple(registry.detect_runs('Latin '+A+B+' '+A+F+B+Z+A+'! End'))
    assert [(run.script, run.text) for run in runs] == [
        (None, 'Latin '), ('khitan', A+B+' '+A+F+B+Z+A), (None, '! End')]
    assert registry.script_for(M) == 'khitan'
    assert registry.script_for(chr(0x18CDB)) is None


@pytest.mark.parametrize(('kind', 'length', 'expected'), [
    ('A', 1, ((0, 1),)),
    ('A', 2, ((0, 0), (0, 2))),
    ('A', 3, ((0, 0), (0, 2), (1, 1))),
    ('A', 4, ((0, 0), (0, 2), (1, 0), (1, 2))),
    ('A', 8, ((0, 0), (0, 2), (1, 0), (1, 2),
              (2, 0), (2, 2), (3, 0), (3, 2))),
    ('B', 2, ((0, 1), (1, 1))),
    ('B', 3, ((0, 1), (1, 0), (1, 2))),
    ('B', 4, ((0, 1), (1, 0), (1, 2), (2, 1))),
    ('B', 8, ((0, 1), (1, 0), (1, 2), (2, 0),
              (2, 2), (3, 0), (3, 2), (4, 1))),
])
def test_unicode_slot_order(kind, length, expected):
    assert slots(KhitanCluster(kind, (0x18B01,)*length)) == expected


class SyntheticFont:
    def glyph(self, cp):
        if cp == 0x18B02:
            return GlyphMetrics(1.25, (-0.2, -0.1, 0.9, 1.3))
        return GlyphMetrics(0.8, (0.1, -0.2, 0.75, 0.7))


@pytest.mark.parametrize('kind', ['A', 'B'])
@pytest.mark.parametrize('length', range(2, 9))
def test_translation_only_and_intrinsic_growth(kind, length):
    layout = KhitanLayout(SyntheticFont())
    cluster = KhitanCluster(kind, (0x18B01, 0x18B02) * 4)
    result = layout.cluster(KhitanCluster(kind, cluster.characters[:length]))
    assert len(result.glyphs) == length
    assert all(g.scale == 1 for g in result.glyphs)
    assert result.depth == 0
    for glyph in result.glyphs:
        assert 0 <= glyph.x
        assert glyph.x + glyph.width <= result.width
        assert 0 <= glyph.y
        assert glyph.y + glyph.height <= result.height
    if length >= 4:
        assert result.height > layout.cluster(KhitanCluster(kind, cluster.characters[:2])).height


def test_odd_final_row_is_ink_centered():
    result = KhitanLayout(SyntheticFont()).cluster(
        KhitanCluster('A', (0x18B01, 0x18B02, 0x18B01)))
    last = result.glyphs[-1]
    assert last.x + last.width / 2 == pytest.approx(result.width / 2)


def test_real_reference_font_preserves_base_glyph_bounds():
    path = Path('tmp/fonts/NotoSerifKhitanSmallScript-Regular.ttf')
    if not path.is_file():
        pytest.skip('official reference font not downloaded')
    font = load_font(path)
    result = KhitanLayout(font).cluster(KhitanCluster('A', (0x18B01,)*8))
    assert len(result.glyphs) == 8
    assert result.height >= 4
    assert all(g.scale == 1 for g in result.glyphs)
    assert all(g.width == pytest.approx(font.glyph(g.codepoint).width) for g in result.glyphs)

def test_linear_and_noto_share_slots_without_shape_changes():
    linear_path = Path(os.environ.get('XSR_LINEAR_FONT',
                       'D:/_INBOX/Download/KhitanSmallLinear.ttf'))
    noto_path = Path('tmp/fonts/NotoSerifKhitanSmallScript-Regular.ttf')
    if not linear_path.is_file() or not noto_path.is_file():
        pytest.skip('both comparison fonts are required')
    fonts = [load_font(path) for path in (noto_path, linear_path)]
    for cluster in (KhitanCluster('A', (0x18B01, 0x18B02)),
                    KhitanCluster('A', (0x18B01, 0x18B02, 0x18B03,
                                         0x18B01, 0x18B02)),
                    KhitanCluster('A', (0x18B01,)*8),
                    KhitanCluster('B', (0x18B01, 0x18B02, 0x18B03, 0x18B01))):
        results = [KhitanLayout(font).cluster(cluster) for font in fonts]
        assert results[0].height == results[1].height
        assert results[0].width == results[1].width
        for font, result in zip(fonts, results):
            assert all(g.scale == 1 for g in result.glyphs)
            assert all(g.width == pytest.approx(font.glyph(g.codepoint).width)
                       for g in result.glyphs)
    linear = fonts[1]
    missing = KhitanLayout(linear).cluster(KhitanCluster('A', (0x18B01, 0x18CFF)))
    assert len(missing.glyphs) == 2

def test_preprocess_discovers_script_fonts_and_gap(tmp_path):
    from xsr.renderer import main
    root = Path(__file__).resolve().parents[1]
    egyptian = root/'tmp/fonts/NewGardiner.ttf'
    khitan = root/'tmp/fonts/NotoSerifKhitanSmallScript-Regular.ttf'
    if not egyptian.is_file() or not khitan.is_file():
        pytest.skip('both reference fonts required')
    source = tmp_path/'mixed.tex'
    source.write_text(
        fr'\xsrEgyptianDefaultFont{{{egyptian.as_posix()}}}' + '\n'
        + fr'\xsrKhitanDefaultFont{{{khitan.as_posix()}}}' + '\n'
        + r'\xsrKhitanClusterGap{0.35}' + '\n'
        + chr(0x13000) + '\n'
        + fr'\xsrKhitanText{{{A} {B}}}', encoding='utf-8')
    assert main(['preprocess', '--input', str(source),
                 '--output-dir', str(tmp_path)]) == 0
    manifest = json.loads((tmp_path / '.xsr/mixed.manifest.json').read_text(encoding='utf-8'))
    assert {run['script'] for run in manifest['runs']} == {'egyptian', 'khitan'}
    assert {run['options'].get('cluster_gap') for run in manifest['runs']
            if run['script'] == 'khitan'} == {0.2, 0.35}
    assert all('cluster_gap' not in run['options'] for run in manifest['runs']
               if run['script'] == 'egyptian')

def test_vertical_host_mode_is_reserved():
    from xsr.khitan.backend import KhitanBackend
    with pytest.raises(XSRError, match='XSR-WRITING-MODE-UNSUPPORTED'):
        KhitanBackend().prepare_options({'writing_mode': 'vertical'})