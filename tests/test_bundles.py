"""Observable cacheless preprocessing, atomic bundles, and transport diagnostics."""
import json
from pathlib import Path
import shutil
import subprocess
import pytest
from fixtures.inline_assets import make_asset
from test_providers import config
from xsr.bundle import write_bundle
from xsr.errors import XSRError
from xsr.renderer import main, default_renderer
from xsr.vector_backend import input_options


def prepare(root, body, *extra):
    source=root/'main.tex';source.write_text(body,encoding='utf-8')
    main(['preprocess','--input',str(source),'--output-dir',str(root),*extra])
    return json.loads((root/'.xsr/main.manifest.json').read_text(encoding='utf-8'))


def many_glyphs(root, count):
    declarations=[];uses=[]
    for i in range(count):
        make_asset(root/f'g{i}.png',100+i,120)
        declarations.append(fr'\GlyphRegister{{g{i}}}{{g{i}.png}}')
        uses.append(fr'\Glyph{{g{i}}}\Glyph[scale=1.2,raise=1pt]{{g{i}}}')
    return ''.join(declarations+uses)


def test_many_glyphs_one_bundle_and_no_default_cache(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    body=many_glyphs(tmp_path,19)
    manifest=prepare(tmp_path,body)
    bundle=tmp_path/manifest['bundle'];first=bundle.read_bytes()
    assert len(manifest['runs'])==38
    assert len({r['digest'] for r in manifest['runs']})==19
    assert {r['response'] for r in manifest['runs']}=={'.xsr/main.responses.tex'}
    assert first.count(b'\\xsrDeclareResponse')==19
    assert {p.name for p in (tmp_path/'.xsr').iterdir()}=={'main.responses.tex','main.manifest.json'}
    assert not list(tmp_path.rglob('.xsr-cache'))
    assert not list(tmp_path.glob('*.xsr-*.tex')) and not list(tmp_path.rglob('*.req'))
    prepare(tmp_path,body)
    assert bundle.read_bytes()==first


def test_reprocess_replaces_entries_without_stale_accumulation(tmp_path):
    make_asset(tmp_path/'glyph.png')
    body=r'\GlyphRegister{g}{glyph.png}\Glyph{g}'
    first=prepare(tmp_path,body)['runs'][0]['digest']
    make_asset(tmp_path/'glyph.png',120,240)
    second=prepare(tmp_path,body)['runs'][0]['digest']
    assert first!=second
    bundle=(tmp_path/'.xsr/main.responses.tex').read_text()
    assert first not in bundle and second in bundle
    prepare(tmp_path,'no glyphs')
    assert second not in (tmp_path/'.xsr/main.responses.tex').read_text()
    assert len(list((tmp_path/'.xsr').iterdir()))==2


def test_provider_no_cache_deduplicates_across_policies_and_cleans_temporary_files(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    options=input_options(config(tmp_path),provider=True)
    from xsr import providers
    original=providers.subprocess.run
    outputs=[]
    def capture(argv,**kwargs):
        assert kwargs['shell'] is False and kwargs['timeout']==30
        outputs.append(Path(argv[argv.index('--output')+1]))
        return original(argv,**kwargs)
    monkeypatch.setattr(providers.subprocess,'run',capture)
    renderer=default_renderer()
    assert renderer.cache is None
    renderer.render('provider','same',options)
    renderer.render('provider','same',options|{'missing_glyph_policy':'error'})
    assert len(outputs)==1 and not outputs[0].parent.exists()
    assert not (tmp_path/'.xsr-cache').exists()
    # A fresh renderer has no cross-run cache.
    default_renderer().render('provider','same',options)
    assert len(outputs)==2 and all(not p.parent.exists() for p in outputs)


@pytest.mark.parametrize('persistent',[False,True])
def test_preprocess_provider_dedup_and_opt_in_cache(tmp_path,persistent):
    config(tmp_path)
    body=r'\xsrKageProvider{provider.json}\xsrKageGlyph{same}\xsrKageGlyph{same}'
    extra=['--cache-dir',str(tmp_path/'chosen-cache')] if persistent else []
    prepare(tmp_path,body,*extra)
    assert len((tmp_path/'calls.jsonl').read_text().splitlines())==1
    assert not (tmp_path/'.xsr-cache').exists()
    assert (tmp_path/'chosen-cache').exists()==persistent
    if persistent:
        assert list((tmp_path/'chosen-cache/providers').glob('*.svg'))
        assert list((tmp_path/'chosen-cache').glob('*.tex'))
    prepare(tmp_path,body,*extra)
    assert len((tmp_path/'calls.jsonl').read_text().splitlines())==(1 if persistent else 2)


@pytest.mark.parametrize('failure',['timeout','oversize','invalid'])
def test_no_cache_provider_preserves_validation_and_cleanup(tmp_path,monkeypatch,failure):
    from xsr import providers
    outputs=[]
    def fake(argv,**kwargs):
        assert kwargs['shell'] is False
        output=Path(argv[argv.index('--output')+1]);outputs.append(output)
        if failure=='timeout':
            raise subprocess.TimeoutExpired(argv,kwargs['timeout'])
        output.write_bytes(b'x'*2_000_001 if failure=='oversize' else b'<svg><script/></svg>')
        return subprocess.CompletedProcess(argv,0)
    monkeypatch.setattr(providers.subprocess,'run',fake)
    code='FAILED' if failure=='timeout' else 'SVG'
    with pytest.raises(XSRError,match='XSR-PROVIDER-'+code):
        default_renderer().render('provider','test',input_options(config(tmp_path),provider=True)|{'missing_glyph_policy':'error'})
    assert all(not p.parent.exists() for p in outputs)


def test_atomic_bundle_failure_preserves_previous_complete_file(tmp_path,monkeypatch):
    path=tmp_path/write_bundle(tmp_path,'main',{'A'*32:'old'})
    old=path.read_bytes()
    original=Path.replace
    def fail(source,target):
        if target==path:
            raise OSError('simulated replace failure')
        return original(source,target)
    monkeypatch.setattr(Path,'replace',fail)
    with pytest.raises(OSError,match='simulated'):
        write_bundle(tmp_path,'main',{'B'*32:'new'})
    assert path.read_bytes()==old
    assert list(path.parent.iterdir())==[path]


@pytest.mark.skipif(shutil.which('xelatex') is None,reason='XeLaTeX unavailable')
@pytest.mark.parametrize('has_bundle',[False,True])
def test_missing_bundle_or_digest_is_typed(tmp_path,has_bundle):
    from test_vector_tex import compile_document
    make_asset(tmp_path/'glyph.png')
    if has_bundle:
        write_bundle(tmp_path,'vector',{})
    output=compile_document(tmp_path,r'\Glyph{g}',r'\GlyphRegister{g}{glyph.png}',mode='preprocess',success=False)
    assert ('XSR-RESPONSE-MISSING' if has_bundle else 'XSR-BUNDLE-MISSING') in output
    assert not list(tmp_path.rglob('*.req'))


@pytest.mark.skipif(shutil.which('xelatex') is None,reason='XeLaTeX unavailable')
def test_many_glyphs_compile_without_shell_or_request_files(tmp_path):
    from test_vector_tex import compile_document
    body=many_glyphs(tmp_path,19)
    compile_document(tmp_path,body,mode='preprocess',prepare=True)
    assert len(list((tmp_path/'.xsr').glob('*.responses.tex')))==1
    assert not list(tmp_path.glob('*.xsr-*.tex')) and not list(tmp_path.rglob('*.req'))
    assert not (tmp_path/'.xsr-cache').exists()


@pytest.mark.skipif(shutil.which('xelatex') is None,reason='XeLaTeX unavailable')
def test_auto_mode_uses_bundle_without_provider(tmp_path):
    from test_vector_tex import compile_document
    config(tmp_path)
    body=r'\xsrKageGlyph{same}'
    preamble=r'\xsrKageProvider{provider.json}'
    compile_document(tmp_path,body,preamble,mode='preprocess',prepare=True)
    compile_document(tmp_path,body,preamble,mode='auto')
    assert len((tmp_path/'calls.jsonl').read_text().splitlines())==1
    assert not list(tmp_path.glob('*.req'))



@pytest.mark.skipif(shutil.which('xelatex') is None,reason='XeLaTeX unavailable')
def test_separate_output_directory_with_no_shell(tmp_path):
    import os
    from test_vector_tex import ROOT
    make_asset(tmp_path/'glyph.png')
    source=tmp_path/'main.tex'
    source.write_text(r'\documentclass{article}\usepackage[mode=preprocess]{xetex-stack-renderer}'
                      r'\GlyphRegister{g}{glyph.png}\begin{document}\Glyph{g}\end{document}')
    output=tmp_path/'build';output.mkdir()
    main(['preprocess','--input',str(source),'--output-dir',str(output),'--tex-workdir',str(tmp_path)])
    env=os.environ.copy();env['TEXINPUTS']=str(ROOT/'tex')+os.pathsep+env.get('TEXINPUTS','')
    result=subprocess.run(['xelatex','-no-shell-escape','-output-directory=build',
                           '-interaction=nonstopmode','-halt-on-error','main.tex'],cwd=tmp_path,
                          env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
    assert result.returncode==0,result.stdout
    assert not list(tmp_path.rglob('*.req'))
    assert not (tmp_path/'.xsr').exists() and (output/'.xsr/main.responses.tex').exists()



@pytest.mark.skipif(shutil.which('xelatex') is None,reason='XeLaTeX unavailable')
@pytest.mark.parametrize('persistent',[False,True])
def test_shell_cleans_fixed_scratch_pair_and_opt_in_cache(tmp_path,persistent):
    from test_vector_tex import compile_document
    config(tmp_path)
    mode='shell,cache-dir=chosen-cache' if persistent else 'shell'
    compile_document(tmp_path,r'\xsrKageGlyph{same}\xsrKageGlyph{same}',
                     r'\xsrKageProvider{provider.json}',mode=mode)
    assert len((tmp_path/'calls.jsonl').read_text().splitlines())==1
    assert not list(tmp_path.glob('*.req')) and not list(tmp_path.glob('*.xsr-*.tex'))
    assert not (tmp_path/'.xsr-cache').exists()
    assert (tmp_path/'chosen-cache').exists()==persistent


@pytest.mark.skipif(shutil.which('xelatex') is None,reason='XeLaTeX unavailable')
def test_bundle_runtime_geometry_changes_with_font_scale_and_raise(tmp_path):
    import re
    from test_vector_tex import compile_document
    from xsr.inline import layout_inline, resolve_asset, IdeographicCell
    path=make_asset(tmp_path/'glyph.png',120,240)
    body=(r'\setbox0=\hbox{\Glyph{g}}\typeout{BUNDLE-A=\the\wd0,\the\ht0,\the\dp0}'
          r'{\Large\setbox0=\hbox{\Glyph[scale=1.5,raise=2pt]{g}}'
          r'\typeout{BUNDLE-B=\the\wd0,\the\ht0,\the\dp0}\box0}')
    output=compile_document(tmp_path,body,r'\GlyphRegister{g}{glyph.png}',mode='preprocess',prepare=True)
    for label,cell,scale,raise_by in [('A',10,1,0),('B',14.4,1.5,2)]:
        match=re.search('BUNDLE-'+label+r'=([\d.-]+)pt,([\d.-]+)pt,([\d.-]+)pt',output)
        expected=layout_inline(resolve_asset(path),IdeographicCell(cell,cell/2),scale=scale,raise_by=raise_by)
        assert tuple(map(float,match.groups()))==pytest.approx((expected.advance,expected.height,expected.depth),abs=.004)
    assert (tmp_path/'.xsr/vector.responses.tex').read_text().count(r'\xsrDeclareResponse')==1
