import json
from pathlib import Path
import pytest
from xsr.errors import XSRError
from xsr.font_metrics import encode_path,decode_path,tex_font_path
from xsr.preprocess import discover_sources
from xsr.renderer import main


def test_path_encoding_roundtrips_unicode_and_separators(tmp_path):
    for spelling in ('/home/user/字型 font.ttf',r'C:\Fonts\字型 font.ttf',str(tmp_path/'αβ'/'日本語.ttf')):
        assert decode_path(encode_path(spelling))==spelling
        assert encode_path(spelling).isascii()
    with pytest.raises(XSRError,match='XSR-REQUEST'):
        decode_path('not-hex')


def test_recursive_discovery_deduplicates_and_ignores_comments(tmp_path):
    root=tmp_path/'main.tex'
    root.write_text(r'\input{chapter}\input{chapter}'+'\n% \\input{missing}',encoding='utf-8')
    child=tmp_path/'chapter.tex'
    child.write_text('plain text',encoding='utf-8')
    assert list(discover_sources([root]))==[root,child]
    child.write_text(r'\include{main}',encoding='utf-8')
    with pytest.raises(XSRError,match='cyclic input'):
        discover_sources([root])


def test_source_and_macro_input_errors(tmp_path):
    with pytest.raises(XSRError,match='XSR-SOURCE-MISSING'):
        discover_sources([tmp_path/'missing.tex'])
    root=tmp_path/'main.tex'
    root.write_text(r'\input{\dynamic}',encoding='utf-8')
    with pytest.raises(XSRError,match='literal filename'):
        discover_sources([root])


def test_multiple_inputs_fonts_and_repeated_runs(tmp_path,font_options):
    a,b=tmp_path/'a.tex',tmp_path/'b.tex'
    a.write_text(chr(0x13000)+' '+chr(0x13000),encoding='utf-8')
    b.write_text(chr(0x13153),encoding='utf-8')
    output=tmp_path/'out'
    args=['preprocess','--input',str(a),'--input',str(b),'--output-dir',str(output),
          '--font',decode_path(font_options['font_codepoints'])]
    assert main(args)==0
    manifest=(output/'a.xsr-manifest.json').read_text(encoding='utf-8')
    assert len(json.loads(manifest)['sources'])==2
    assert len(list(output.glob('*.xsr-*.tex')))==2
    assert main(args)==0
    assert (output/'a.xsr-manifest.json').read_text(encoding='utf-8')==manifest


def test_font_error_categories(tmp_path):
    from xsr.font_metrics import load_font
    with pytest.raises(XSRError,match='XSR-FONT-MISSING'):
        load_font(tmp_path/'missing.ttf')
    path=tmp_path/'bad.ttf'
    path.write_bytes(b'not a font')
    with pytest.raises(XSRError,match='XSR-FONT-FORMAT'):
        load_font(path)


def test_malformed_request_returns_diagnostic_response(tmp_path,capsys):
    path=tmp_path/'bad.req'
    path.write_text('XSR999\n')
    output=tmp_path/'test.xsr-invalid.tex'
    with pytest.raises(SystemExit) as error:
        main(['render','--backend','egyptian','--input',str(path),'--output',str(output),'--cache-dir',str(tmp_path/'cache')])
    assert error.value.code==2
    assert '\\xsrRendererError{XSR-REQUEST}' in output.read_text()
    assert 'Traceback' not in capsys.readouterr().err
