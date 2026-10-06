import math
from pathlib import Path
import pytest
from xsr.errors import XSRError
from xsr.inline import GlyphRegistry, VisualAsset, IdeographicCell, layout_inline, resolve_asset, vector_asset, inline_tex
from xsr.vector import import_svg
from xsr.synthetic import XSRWarning
from fixtures.inline_assets import make_asset


def test_registration_repeat_and_duplicate(tmp_path):
    path=make_asset(tmp_path/'glyph.png')
    registry=GlyphRegistry(tmp_path)
    registry.register('test','glyph.png');registry.register('test','glyph.png')
    assert registry.resolve('test') == registry.resolve('test') == resolve_asset(path)
    with pytest.raises(XSRError,match='DUPLICATE'):
        registry.register('test','other.png')
    with pytest.raises(XSRError,match='UNKNOWN'):
        registry.resolve('absent')
    with pytest.raises(XSRError,match='LABEL'):
        registry.register('',path)


@pytest.mark.parametrize('extension',['png','jpg','jpeg','pdf','svg'])
def test_source_detection_and_identity(tmp_path,extension):
    path=make_asset(tmp_path/('glyph.'+extension),120,240)
    asset=resolve_asset(path)
    assert asset.source_class == ('vector' if extension=='svg' else 'image')
    assert asset.aspect_ratio == .5
    assert asset.identity[0] == path.resolve().as_posix()
    assert len(asset.identity[1])==64
    assert r'\xsrInlineGlyph' in inline_tex(asset)


@pytest.mark.parametrize('ratio',[1,.5,2,.25,4,.01,100])
@pytest.mark.parametrize('source_class,alpha',[('image',1.1),('vector',1)])
@pytest.mark.parametrize('scale',[.25,1,2.75])
def test_geometric_mean_and_aspect_invariance(ratio,source_class,alpha,scale):
    asset=VisualAsset(100*ratio,100,source_class,None,('test',''))
    if ratio>16 or ratio<1/16:
        with pytest.warns(XSRWarning,match='ASPECT'):
            glyph=layout_inline(asset,IdeographicCell(12,4.2),scale=scale,raise_by=1.25)
    else:
        glyph=layout_inline(asset,IdeographicCell(12,4.2),scale=scale,raise_by=1.25)
    assert glyph.canvas_width/glyph.canvas_height == pytest.approx(ratio)
    assert math.sqrt(glyph.canvas_width*glyph.canvas_height)==pytest.approx(alpha*12*scale)
    assert glyph.height == pytest.approx(max(0,glyph.canvas_height+glyph.shift))
    assert glyph.depth == pytest.approx(max(0,-glyph.shift))
    assert glyph.advance == pytest.approx(glyph.width+2*glyph.side_bearing)
    if source_class=='image':
        assert glyph.shift+glyph.canvas_height/2 == pytest.approx(4.2+1.25)
        assert glyph.advance == pytest.approx(.96*glyph.canvas_width)
    else:
        assert glyph.side_bearing==0
        assert glyph.shift==pytest.approx(-1.8+1.25)


def test_tall_and_wide_are_not_clamped():
    tall=layout_inline(VisualAsset(1,4,'image',None,('','')))
    wide=layout_inline(VisualAsset(4,1,'image',None,('','')))
    assert tall.canvas_height==pytest.approx(2.2)
    assert tall.height==pytest.approx(1.6) and tall.depth==pytest.approx(.6)
    assert wide.canvas_width==pytest.approx(2.2)
    assert wide.advance>2


@pytest.mark.parametrize('scale',[0,-1,float('nan'),float('inf')])
def test_invalid_scale(scale):
    with pytest.raises(XSRError,match='GEOMETRY'):
        layout_inline(VisualAsset(1,1,'image',None,('','')),scale=scale)


def test_vector_outside_design_space_has_honest_metrics():
    asset=vector_asset(import_svg('<svg viewBox="0 0 100 100"><path d="M-50 -50H150V150H-50Z"/></svg>'))
    glyph=layout_inline(asset)
    assert glyph.canvas_width==glyph.canvas_height==1
    assert glyph.width==glyph.advance==2
    assert glyph.height==1.5 and glyph.depth==.5


def test_generated_and_manual_svg_converge(tmp_path):
    path=make_asset(tmp_path/'external.svg',100,400)
    manual=resolve_asset(path)
    generated=vector_asset(import_svg(path.read_bytes()),manual.identity)
    assert layout_inline(manual)==layout_inline(generated)
    assert inline_tex(manual)==inline_tex(generated)


@pytest.mark.parametrize('extension',['png','jpg','pdf','gif'])
def test_bad_asset_is_typed(tmp_path,extension):
    path=tmp_path/('bad.'+extension);path.write_bytes(b'invalid')
    with pytest.raises(XSRError,match='ASSET-FORMAT'):
        resolve_asset(path)


def test_pdf_rotation_and_canvas(tmp_path):
    import fitz
    path=make_asset(tmp_path/'rotated.pdf',40,80)
    with fitz.open(path) as doc:
        doc[0].set_rotation(90)
        doc.saveIncr()
    assert resolve_asset(path).aspect_ratio==2


def test_pixels_not_dpi_determine_aspect(tmp_path):
    from PIL import Image
    path=tmp_path/'dpi.png'
    Image.new('RGB',(60,120),'white').save(path,dpi=(72,144))
    assert resolve_asset(path).aspect_ratio==.5
