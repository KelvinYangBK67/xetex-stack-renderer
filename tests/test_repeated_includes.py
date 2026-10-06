"""Repeated includes execute in each scope; only active recursion is a cycle."""
import json
from pathlib import Path
import pytest
from xsr.errors import XSRError
from xsr.preprocess import discover_sources
from xsr.policy_scopes import policy_spans
from xsr.renderer import main
from test_providers import config


def test_repeated_include_styles_and_policies(tmp_path):
    config(tmp_path)
    source = tmp_path/'main.tex'
    source.write_text(r'\xsrKageProvider{provider.json}'
        r'{\xsrKageStyle{sans}\xsrMissingGlyphPolicy{error}\input{child}}'
        r'{\xsrKageStyle{serif}\xsrMissingGlyphPolicy{box}\input{child}}')
    (tmp_path/'child.tex').write_text(r'\xsrKageGlyph{same}')
    main(['preprocess','--input',str(source),'--output-dir',str(tmp_path)])
    runs=json.loads((tmp_path / '.xsr/main.manifest.json').read_text())['runs']
    assert [(r['options']['style'],r['options']['missing_glyph_policy']) for r in runs] == [('sans','error'),('serif','box')]
    assert len((tmp_path/'calls.jsonl').read_text().splitlines()) == 2
    spans=policy_spans(discover_sources([source]))[(tmp_path/'child.tex').resolve()]
    assert [value for start,end,value in spans if start == 0] == ['error','box']


def test_repeated_explicit_input_executes_again(tmp_path):
    config(tmp_path)
    source=tmp_path/'main.tex'
    source.write_text(r'\xsrKageProvider{provider.json}\xsrKageGlyph{same}')
    main(['preprocess','--input',str(source),'--input',str(source),'--output-dir',str(tmp_path)])
    runs=json.loads((tmp_path / '.xsr/main.manifest.json').read_text())['runs']
    assert len(runs)==2
    assert len((tmp_path/'calls.jsonl').read_text().splitlines())==1


def test_include_resolution_is_parent_first(tmp_path):
    sub=tmp_path/'sub';sub.mkdir()
    root=tmp_path/'main.tex';root.write_text(r'\input{sub/parent}')
    (sub/'parent.tex').write_text(r'\input{child}')
    (sub/'child.tex').write_text(r'\xsrMissingGlyphPolicy{error}')
    (tmp_path/'child.tex').write_text(r'\xsrMissingGlyphPolicy{box}')
    sources=discover_sources([root])
    assert (sub/'child.tex') in sources and (tmp_path/'child.tex') not in sources
    assert policy_spans(sources)[sub/'child.tex'][-1][-1]=='error'


def test_active_cycle_still_rejected(tmp_path):
    a=tmp_path/'a.tex';b=tmp_path/'b.tex'
    a.write_text(r'\input{b}');b.write_text(r'\input{a}')
    with pytest.raises(XSRError,match='cyclic'):
        discover_sources([a])



def test_font_run_included_under_each_policy(tmp_path):
    from test_font_metrics import make_font
    font=tmp_path/'font.ttf';make_font(font)
    source=tmp_path/'main.tex'
    source.write_text(r'\xsrEgyptianDefaultFont{font.ttf}'
        r'{\xsrMissingGlyphPolicy{error}\input{child}}'
        r'{\xsrMissingGlyphPolicy{box}\input{child}}')
    (tmp_path/'child.tex').write_text(chr(0x13000),encoding='utf-8')
    main(['preprocess','--input',str(source),'--output-dir',str(tmp_path)])
    runs=json.loads((tmp_path / '.xsr/main.manifest.json').read_text())['runs']
    assert {r['options'].get('missing_glyph_policy','box') for r in runs}=={'box','error'}
    assert len({r['digest'] for r in runs})==2
