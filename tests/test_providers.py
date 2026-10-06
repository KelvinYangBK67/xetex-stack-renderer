import json
from pathlib import Path
import sys
import pytest
from xsr.errors import XSRError
from xsr.renderer import default_renderer
from xsr.synthetic import XSRWarning
from xsr.vector_backend import input_options

FIXTURES = Path(__file__).parent / 'fixtures'


def config(tmp_path, **extra):
    path = tmp_path/'provider.json'
    path.write_text(json.dumps({'executable': sys.executable,
        'prefix_args': [str((FIXTURES/'synthetic_provider.py').resolve()), '--log', str(tmp_path/'calls.jsonl')],
        **extra}), encoding='utf-8')
    return path


def test_transport_cache_and_metadata(tmp_path):
    path = config(tmp_path, options={'weight': 2}, metadata={'engine_version': 'test', 'dataset_digest': 'synthetic'})
    options = input_options(path, provider=True) | {'style': 'sans'}
    renderer = default_renderer(tmp_path/'cache')
    glyph = '字; $(echo nope) & "quoted"'
    a = renderer.render('provider', glyph, options)
    assert a == default_renderer(tmp_path/'cache').render('provider', glyph, options)
    calls = (tmp_path/'calls.jsonl').read_text().splitlines()
    assert len(calls) == 1
    assert json.loads(calls[0]) == {'glyph': glyph, 'style': 'sans', 'options': {'weight': 2}}
    metadata = json.loads(next((tmp_path/'cache/providers').glob('*.json')).read_text())
    assert len(metadata['svg_sha256']) == 64
    assert metadata['provider']['metadata']['engine_version'] == 'test'
    renderer.render('provider', glyph, options | {'style': 'serif'})
    renderer.render('provider', 'second', options)
    assert len((tmp_path/'calls.jsonl').read_text().splitlines()) == 3


@pytest.mark.parametrize('glyph,code', [('missing','MISSING'),('empty','MISSING'),('failure','FAILED'),('invalid','SVG')])
def test_provider_errors_and_fallback(tmp_path, glyph, code):
    options = input_options(config(tmp_path), provider=True)
    renderer = default_renderer(tmp_path/'cache')
    with pytest.raises(XSRError, match='XSR-PROVIDER-'+code):
        renderer.render('provider', glyph, options | {'missing_glyph_policy': 'error'})
    with pytest.warns(XSRWarning, match='XSR-PROVIDER-'+code):
        result = renderer.render('provider', glyph, options)
    assert r'\xsrVectorWarning{XSR-PROVIDER-'+code+'}' in result
    assert r'\xsrInlineGlyph{{baseline}{0}}{1}{1}{0}{0}{1}{1}{0}' in result


def test_unavailable(tmp_path):
    renderer = default_renderer(tmp_path/'cache')
    with pytest.warns(XSRWarning, match='UNAVAILABLE'):
        renderer.render('provider', 'abc', {})
    with pytest.raises(XSRError, match='UNAVAILABLE'):
        renderer.render('provider', 'abc', {'missing_glyph_policy': 'error'})
    with pytest.warns(XSRWarning, match='UNAVAILABLE'):
        renderer.render('provider', 'abc', input_options(config(tmp_path, executable='nonexistent-xsr-provider'), provider=True))


def test_direct_unicode_path_change_and_stale(tmp_path):
    path = tmp_path/'字形.svg'
    path.write_bytes((FIXTURES/'square.svg').read_bytes())
    options = input_options(path)
    renderer = default_renderer(tmp_path/'cache')
    a = renderer.render('vector', '', options)
    assert a == renderer.render('vector', '', options)
    assert len(list((tmp_path/'cache').glob('*.tex'))) == 1
    path.write_text('<svg viewBox="0 0 200 200"><path d="M0 0L200 200L0 200Z"/></svg>')
    with pytest.raises(XSRError, match='STALE'):
        renderer.render('vector', '', options)
    assert a != renderer.render('vector', '', input_options(path))
    assert len(list((tmp_path/'cache').glob('*.tex'))) == 2

@pytest.mark.parametrize('extra', [
    {'prefix_args': 'unsafe string'}, {'executable': 'wrapper.cmd'},
    {'options': []}, {'timeout': 0}, {'timeout': 301}, {'executable': ''}])
def test_invalid_provider_configuration(tmp_path, extra):
    from xsr.providers import ProviderConfig
    with pytest.raises(XSRError, match='XSR-PROVIDER-CONFIG'):
        ProviderConfig.read(config(tmp_path, **extra))


def test_config_revision_invalidates_generation(tmp_path):
    path = config(tmp_path, metadata={'dataset_version':'1'})
    renderer = default_renderer(tmp_path/'cache')
    renderer.render('provider', 'test', input_options(path, provider=True))
    path = config(tmp_path, metadata={'dataset_version':'2'})
    renderer.render('provider', 'test', input_options(path, provider=True))
    assert len((tmp_path/'calls.jsonl').read_text().splitlines()) == 2

def test_preprocess_external_identifier_is_not_font_text(tmp_path):
    from xsr.renderer import main
    config(tmp_path)
    source = tmp_path/'external.tex'
    glyph = chr(0x13000)+chr(0x18CFF)
    source.write_text(r'\xsrKageProvider{provider.json}'+fr'\xsrKageGlyph{{{glyph}}}', encoding='utf-8')
    assert main(['preprocess','--input',str(source),'--output-dir',str(tmp_path)]) == 0
    manifest = json.loads((tmp_path / '.xsr/external.manifest.json').read_text())
    assert [run['script'] for run in manifest['runs']] == ['provider']
    assert json.loads((tmp_path/'calls.jsonl').read_text())['glyph'] == glyph


def test_preprocess_included_scoped_provider_styles(tmp_path):
    from xsr.renderer import main
    config(tmp_path)
    source = tmp_path/'external.tex'
    source.write_text(r'\xsrKageProvider{provider.json}{\xsrKageStyle{sans}\input{child}}\xsrKageGlyph{same}', encoding='utf-8')
    (tmp_path/'child.tex').write_text(r'\xsrKageGlyph{same}\xsrKageGlyph{same}')
    main(['preprocess','--input',str(source),'--output-dir',str(tmp_path)])
    calls = [json.loads(line) for line in (tmp_path/'calls.jsonl').read_text().splitlines()]
    assert [call['style'] for call in calls] == ['sans','serif']
