"""Source-independent inline assets, policy, metrics, registration and TeX payloads.

Only canvas metadata is read. Pixels and PDF content are never rewritten.
Geometry is uniform; use-site scale/raise and the current cell remain runtime
TeX inputs, so one cached response works at every surrounding font size.
"""
from dataclasses import dataclass
import hashlib
from io import BytesIO
import math
from pathlib import Path
from PIL import Image
from pypdf.errors import PyPdfError
from .errors import XSRError
from .font_metrics import encode_path, tex_font_path
from .synthetic import warn
from .vector import ExternalVectorGlyph, import_svg, number, paths_tex

INLINE_VERSION = 'inline-0.10-optical-1'


@dataclass(frozen=True)
class GlyphPolicy:
    alpha: float
    alignment: str
    side_bearing_fraction: float = 0.
    vertical_bias_fraction: float = 0.


VECTOR_POLICY = GlyphPolicy(1., 'baseline')
# Small, explicit image-canvas side bearings, like ordinary font side bearings.
# The complete canvas is drawn; this is spacing, never cropping or distortion.
IMAGE_POLICY = GlyphPolicy(1.10, 'center', side_bearing_fraction=-.02,
                           vertical_bias_fraction=-.12)


@dataclass(frozen=True)
class ImagePayload:
    path: str
    digest: str
    format: str


@dataclass(frozen=True)
class VisualAsset:
    intrinsic_width: float
    intrinsic_height: float
    source_class: str
    payload: ExternalVectorGlyph | ImagePayload
    identity: tuple[str, str]

    @property
    def aspect_ratio(self):
        return self.intrinsic_width/self.intrinsic_height


@dataclass(frozen=True)
class IdeographicCell:
    size: float = 1.
    center: float = .5

    @property
    def depth(self):
        return self.size/2-self.center


@dataclass(frozen=True)
class InlineGlyph:
    asset: VisualAsset
    canvas_width: float
    canvas_height: float
    width: float
    advance: float
    height: float
    depth: float
    shift: float
    side_bearing: float
    bounds: tuple[float, float, float, float]

    @property
    def payload(self):
        return self.asset.payload

    @property
    def identity(self):
        return self.asset.identity


def vector_asset(glyph, identity=('', '')):
    return VisualAsset(glyph.design_width, glyph.design_height, 'vector', glyph, identity)


def resolve_asset(path):
    path = Path(tex_font_path(path))
    try:
        data = path.read_bytes()
    except OSError as error:
        raise XSRError('XSR-ASSET-MISSING', str(error)) from error
    digest = hashlib.sha256(data).hexdigest()
    suffix = path.suffix.lower()
    if suffix == '.svg':
        return vector_asset(import_svg(data), (path.as_posix(), digest))
    try:
        if suffix in ('.png', '.jpg', '.jpeg'):
            # Pillow.open reads headers; no load, conversion, crop or save.
            with Image.open(BytesIO(data)) as image:
                expected = 'PNG' if suffix == '.png' else 'JPEG'
                if image.format != expected:
                    raise ValueError('file contents do not match the image extension')
                width, height = image.size
                if getattr(image, 'n_frames', 1) != 1:
                    raise ValueError('provide a single-frame glyph image')
            fmt = expected.lower()
        elif suffix == '.pdf':
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data), strict=True)
            if reader.is_encrypted or len(reader.pages) != 1:
                raise ValueError('provide a single-page, unencrypted PDF glyph')
            page = reader.pages[0]
            width, height = float(page.mediabox.width), float(page.mediabox.height)
            rotation = page.rotation % 360
            if rotation not in (0,90,180,270):
                raise ValueError('PDF page rotation must be a multiple of 90 degrees')
            if rotation in (90,270):
                width, height = height, width
            fmt = 'pdf'
        else:
            raise XSRError('XSR-ASSET-FORMAT', 'supported glyph assets: SVG, PNG, JPEG/JPG, PDF')
        if not all(math.isfinite(v) and v > 0 for v in (width,height)):
            raise ValueError('canvas dimensions must be finite and positive')
    except XSRError:
        raise
    except (ValueError, OSError, KeyError, TypeError, PyPdfError) as error:
        raise XSRError('XSR-ASSET-FORMAT', f'invalid {suffix} glyph asset: {error}') from error
    return VisualAsset(float(width), float(height), 'image',
                       ImagePayload(path.as_posix(), hashlib.md5(data, usedforsecurity=False).hexdigest().upper(), fmt),
                       (path.as_posix(), digest))


def asset_policy(asset):
    return IMAGE_POLICY if asset.source_class == 'image' else VECTOR_POLICY


def layout_inline(asset, cell=IdeographicCell(), *, scale=1., raise_by=0., policy=None):
    policy = policy or asset_policy(asset)
    if not all(math.isfinite(v) for v in (cell.size,cell.center,scale,raise_by,policy.alpha,policy.vertical_bias_fraction)) or min(cell.size,scale,policy.alpha) <= 0:
        raise XSRError('XSR-INLINE-GEOMETRY', 'cell, alpha and uniform scale must be finite and positive; raise must be finite')
    ratio = asset.aspect_ratio
    if ratio > 16 or ratio < 1/16:
        warn('XSR-INLINE-ASPECT', f'extreme canvas aspect ratio {ratio:g}; retained without clamping')
    width = policy.alpha*cell.size*scale*math.sqrt(ratio)
    height = policy.alpha*cell.size*scale/math.sqrt(ratio)
    shift = ((cell.center-height/2 if policy.alignment == 'center' else -cell.depth)
             + policy.vertical_bias_fraction*cell.size*scale + raise_by)
    bounds = (0.,0.,width,height)
    if isinstance(asset.payload, ExternalVectorGlyph):
        x0,y0,x1,y1 = asset.payload.bounds
        bounds = (min(0.,x0*height),min(0.,y0*height),max(width,x1*height),max(height,y1*height))
    side = width*policy.side_bearing_fraction
    box_width = bounds[2]-bounds[0]
    return InlineGlyph(asset,width,height,box_width,box_width+2*side,
                       max(0.,bounds[3]+shift),max(0.,-bounds[1]-shift),shift,side,bounds)


def inline_tex(asset):
    """One class-policy-driven emitter for files, provider results and vectors."""
    policy = asset_policy(asset)
    glyph = layout_inline(asset)
    if isinstance(asset.payload, ExternalVectorGlyph):
        payload = paths_tex(asset.payload)
    else:
        payload = (r'\xsrInlineImage{' + encode_path(asset.payload.path) + '}{'
                   + asset.payload.digest + '}{' + asset.payload.format + '}')
    values = (glyph.canvas_width,glyph.canvas_height,*glyph.bounds,policy.side_bearing_fraction)
    # Pack alignment and optical bias in one policy argument (TeX has nine slots).
    return (r'\xsrInlineGlyph{{' + policy.alignment + '}{'
            + number(policy.vertical_bias_fraction) + '}}'
            + ''.join('{' + number(v) + '}' for v in values) + '{' + payload + '}')


class GlyphRegistry:
    """Intentionally small label -> file registry, independent of acquisition."""
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or Path.cwd()).resolve()
        self._files = {}

    def register(self, label, file):
        if not isinstance(label,str) or not label.strip():
            raise XSRError('XSR-GLYPH-LABEL', 'glyph label must be a nonempty string')
        file = str(file)
        if label in self._files and self._files[label] != file:
            raise XSRError('XSR-GLYPH-DUPLICATE', f'label already registered: {label}')
        self._files[label] = file

    def file(self, label):
        try:
            return self._files[label]
        except KeyError as error:
            raise XSRError('XSR-GLYPH-UNKNOWN', f'unregistered glyph label: {label}') from error

    def resolve(self, label):
        return resolve_asset(self.base_dir / self.file(label))
