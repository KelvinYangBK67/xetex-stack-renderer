"""Actual XeLaTeX metrics and PDF payload checks for the shared inline pipeline."""
import re
import shutil
from pathlib import Path
import fitz
import pytest
from fixtures.inline_assets import make_asset
from test_vector_tex import compile_document, ROOT
from xsr.inline import layout_inline, resolve_asset, IdeographicCell
from test_providers import config

pytestmark=pytest.mark.skipif(shutil.which('xelatex') is None,reason='XeLaTeX unavailable')


def measured(output):
    match=re.search(r'INLINE-BOX=([\d.-]+)pt,([\d.-]+)pt,([\d.-]+)pt',output)
    assert match,output
    return tuple(float(v) for v in match.groups())


def box_body(options='',size=''):
    return (size+r'\setbox0=\hbox{\Glyph['+options+r']{test}}'
            +r'\typeout{INLINE-BOX=\the\wd0,\the\ht0,\the\dp0}Before \box0 after.')


@pytest.mark.parametrize('ratio',[1,.5,2,.25,4,32])
@pytest.mark.parametrize('extension',['png','svg'])
def test_honest_metrics_and_payload_ratio(tmp_path,ratio,extension):
    path=make_asset(tmp_path/('glyph.'+extension),int(120*ratio),120)
    preamble=fr'\GlyphRegister{{test}}{{glyph.{extension}}}'
    output=compile_document(tmp_path,box_body(),preamble)
    expected=layout_inline(resolve_asset(path),IdeographicCell(10,5))
    assert measured(output)==pytest.approx((expected.advance,expected.height,expected.depth),abs=.003)
    with fitz.open(tmp_path/'vector.pdf') as pdf:
        if extension=='png':
            assert len(pdf[0].get_images())==1
            bbox=pdf[0].get_image_rects(pdf[0].get_images()[0][0])[0]
            assert bbox.width/bbox.height==pytest.approx(ratio,rel=.002)
        else:
            assert not pdf[0].get_images()
            assert pdf[0].get_drawings()


@pytest.mark.parametrize('extension',['png','jpg','jpeg','pdf','svg'])
def test_no_shell_preprocess_registry_and_repeat(tmp_path,extension):
    make_asset(tmp_path/('字形.'+extension),100,200)
    preamble=fr'\GlyphRegister{{test}}{{字形.{extension}}}\GlyphRegister{{test}}{{字形.{extension}}}'
    compile_document(tmp_path,r'Before \Glyph{test} \Glyph{test} after.',preamble,mode='preprocess',prepare=True)
    assert (tmp_path/'.xsr/vector.responses.tex').read_text().count(r'\xsrDeclareResponse')==1
    assert not list(tmp_path.glob('vector.xsr-*.tex'))
    assert not list(tmp_path.glob('*.req'))
    with fitz.open(tmp_path/'vector.pdf') as pdf:
        assert 'Before' in pdf[0].get_text()
        assert bool(pdf[0].get_images()) == (extension in ('png','jpg','jpeg'))
        if extension in ('pdf','svg'):
            assert pdf[0].get_drawings()


@pytest.mark.parametrize('size,cell',[(r'\small ',9),('',10),(r'\Large ',14.4)])
@pytest.mark.parametrize('extension',['png','svg','jpg','pdf'])
def test_size_scale_and_raise(tmp_path,size,cell,extension):
    path=make_asset(tmp_path/('glyph.'+extension),100,200)
    preamble=fr'\GlyphRegister{{test}}{{glyph.{extension}}}'
    output=compile_document(tmp_path,box_body('scale=1.5,raise=2pt',size),preamble)
    expected=layout_inline(resolve_asset(path),IdeographicCell(cell,cell/2),scale=1.5,raise_by=2)
    assert measured(output)==pytest.approx((expected.advance,expected.height,expected.depth),abs=.004)


@pytest.mark.parametrize('options',['width=10pt','height=10pt','xscale=2','yscale=2','stretch=2','trim=1pt','crop=true','preserve-aspect=false','scale=0','scale=-1','scale=inf'])
def test_forbidden_adjustments(tmp_path,options):
    make_asset(tmp_path/'glyph.png')
    compile_document(tmp_path,box_body(options),r'\GlyphRegister{test}{glyph.png}',success=False)


@pytest.mark.parametrize('preamble,body,code',[
    ('',r'\Glyph{absent}','XSR-GLYPH-UNKNOWN'),
    (r'\GlyphRegister{test}{absent.png}',r'\Glyph{test}','XSR-ASSET-MISSING'),
    (r'\GlyphRegister{test}{a.png}\GlyphRegister{test}{b.png}',r'\Glyph{test}','XSR-GLYPH-DUPLICATE'),
    (r'\GlyphRegister{}{a.png}','test','XSR-GLYPH-LABEL')])
def test_registration_diagnostics(tmp_path,preamble,body,code):
    assert code in compile_document(tmp_path,body,preamble,success=False)


def test_tall_image_expands_actual_line_spacing(tmp_path):
    make_asset(tmp_path/'tall.png',100,400)
    body=r'\noindent Normal one.\par Normal two.\par Tall \Glyph{test} line.\par Normal four.\par Normal five.'
    compile_document(tmp_path,body,r'\GlyphRegister{test}{tall.png}')
    with fitz.open(tmp_path/'vector.pdf') as pdf:
        origins=[]
        for block in pdf[0].get_text('dict')['blocks']:
            for line in block.get('lines',[]):
                for span in line['spans']:
                    if span['text'].startswith(('Normal','Tall')):
                        origins.append(span['origin'][1])
        assert len(origins)==5
        gaps=[b-a for a,b in zip(origins,origins[1:])]
        assert gaps[1]>gaps[0]
        assert gaps[2]>gaps[3]
        assert gaps[0]==pytest.approx(gaps[3],abs=.1)


def test_asymmetric_dpi_does_not_reshape_pixels(tmp_path):
    from PIL import Image
    Image.new('RGB',(60,120),'black').save(tmp_path/'glyph.png',dpi=(72,144))
    compile_document(tmp_path,r'\Glyph{test}',r'\GlyphRegister{test}{glyph.png}')
    with fitz.open(tmp_path/'vector.pdf') as pdf:
        bbox=pdf[0].get_image_rects(pdf[0].get_images()[0][0])[0]
        assert bbox.width/bbox.height==pytest.approx(.5,rel=.002)


def test_rotated_pdf_canvas(tmp_path):
    path=make_asset(tmp_path/'glyph.pdf',40,80)
    with fitz.open(path) as doc:
        doc[0].set_rotation(90);doc.saveIncr()
    output=compile_document(tmp_path,box_body(),r'\GlyphRegister{test}{glyph.pdf}')
    expected=layout_inline(resolve_asset(path),IdeographicCell(10,5))
    assert measured(output)==pytest.approx((expected.advance,expected.height,expected.depth),abs=.003)


def test_provider_and_registration_use_same_vector_metrics(tmp_path):
    config(tmp_path)
    make_asset(tmp_path/'glyph.svg',200,200)
    body=(r'\setbox0=\hbox{\Glyph{test}}\setbox1=\hbox{\xsrKageGlyph{test-glyph}}'
          r'\typeout{COMMON-WIDTH=\the\wd0,\the\wd1}\box0\box1')
    output=compile_document(tmp_path,body,r'\GlyphRegister{test}{glyph.svg}\xsrKageProvider{provider.json}',mode='preprocess',prepare=True)
    assert 'COMMON-WIDTH=10.0pt,10.0pt' in output
    responses=(tmp_path/'.xsr/vector.responses.tex').read_text(encoding='utf-8')
    assert responses.count(r'\xsrInlineGlyph')==2


@pytest.mark.parametrize('extension',['png','svg'])
def test_current_ideographic_font_cell(tmp_path,extension):
    from fontTools.ttLib import TTFont
    from test_font_metrics import make_font
    font=tmp_path/'cell.ttf';make_font(font)
    with TTFont(font) as ft:
        for cmap in ft['cmap'].tables:
            if cmap.isUnicode():
                cmap.cmap.update({0x20:'empty',0x3000:'empty',0x56FD:'sign'})
        ft['hmtx'].metrics['empty']=(1200,0)
        ft.save(tmp_path/'ideographic.ttf')
    path=make_asset(tmp_path/('glyph.'+extension))
    body=(r'{\font\cellfont="[ideographic.ttf]" at 10pt\cellfont'
          r'\setbox0=\hbox{\Glyph{test}}'
          r'\typeout{INLINE-BOX=\the\wd0,\the\ht0,\the\dp0}\box0}')
    output=compile_document(tmp_path,body,fr'\GlyphRegister{{test}}{{glyph.{extension}}}')
    expected=layout_inline(resolve_asset(path),IdeographicCell(12,2.5))
    assert measured(output)==pytest.approx((expected.advance,expected.height,expected.depth),abs=.004)


def test_negative_raise_and_all_sizes_share_response(tmp_path):
    make_asset(tmp_path/'glyph.png')
    body=box_body('raise=-3pt')+r'{\small\Glyph{test}}{\Large\Glyph[scale=2]{test}}'
    output=compile_document(tmp_path,body,r'\GlyphRegister{test}{glyph.png}',mode='preprocess',prepare=True)
    assert measured(output)==pytest.approx((10.56,6.3,4.7),abs=.003)
    assert (tmp_path/'.xsr/vector.responses.tex').read_text().count(r'\xsrDeclareResponse')==1
    assert not list(tmp_path.glob('vector.xsr-*.tex'))


def test_changed_image_invalidates_response(tmp_path):
    path=make_asset(tmp_path/'glyph.png')
    preamble=r'\GlyphRegister{test}{glyph.png}'
    first=compile_document(tmp_path,box_body(),preamble,mode="preprocess",prepare=True)
    make_asset(path,120,240)
    second=compile_document(tmp_path,box_body(),preamble,mode="preprocess",prepare=True)
    assert measured(first)!=measured(second)
    assert not list(tmp_path.glob('vector.xsr-*.tex'))
    assert (tmp_path/'.xsr/vector.responses.tex').read_text().count(r'\xsrDeclareResponse')==1



def test_pdf_uses_full_mediabox_without_cropping(tmp_path):
    path=make_asset(tmp_path/'glyph.pdf',120,240)
    with fitz.open(path) as doc:
        doc[0].set_cropbox(fitz.Rect(30,60,90,180));doc.saveIncr()
    output=compile_document(tmp_path,box_body(),r'\GlyphRegister{test}{glyph.pdf}')
    expected=layout_inline(resolve_asset(path),IdeographicCell(10,5))
    assert measured(output)==pytest.approx((expected.advance,expected.height,expected.depth),abs=.003)
    with fitz.open(tmp_path/'vector.pdf') as pdf:
        drawings=pdf[0].get_drawings()
        assert len(drawings)==4
        # Union coordinates explicitly: horizontal/vertical line rectangles have
        # zero area and Rect.include_rect treats those as empty.
        rect=fitz.Rect(min(d['rect'].x0 for d in drawings),min(d['rect'].y0 for d in drawings),
                       max(d['rect'].x1 for d in drawings),max(d['rect'].y1 for d in drawings))
        # Complete original ink spans 60% of the MediaBox even with a CropBox.
        assert rect.width==pytest.approx(expected.canvas_width*.6*72/72.27,abs=.02)
        assert rect.height==pytest.approx(expected.canvas_height*.6*72/72.27,abs=.02)
    from pypdf import PdfReader
    objects=PdfReader(tmp_path/'vector.pdf').pages[0]['/Resources']['/XObject']
    assert [list(obj.get_object()['/BBox']) for obj in objects.values()]==[[0,0,120,240]]


def test_preprocess_literal_options_allow_whitespace(tmp_path):
    make_asset(tmp_path/'glyph.png')
    compile_document(tmp_path,'Before \\Glyph \n [scale=1.2,\nraise=1pt]{test} after.',
                     r'\GlyphRegister{test}{glyph.png}',mode='preprocess',prepare=True)



def test_old_policy_bundle_cannot_be_reused(tmp_path):
    from xsr.bundle import write_bundle
    from xsr.renderer import request_digest
    from xsr.vector_backend import input_options
    path=make_asset(tmp_path/'glyph.png')
    old=request_digest('asset','inline-0.10','',input_options(path,spelling='glyph.png'))
    write_bundle(tmp_path,'vector',{old:r'\typeout{OLD-POLICY-WAS-USED}'})
    output=compile_document(tmp_path,r'\Glyph{test}',r'\GlyphRegister{test}{glyph.png}',mode='preprocess',success=False)
    assert 'XSR-RESPONSE-MISSING' in output and 'OLD-POLICY-WAS-USED' not in output
