# xetex-stack-renderer

XSR **0.10** is a Unicode-driven stack renderer for XeTeX/XeLaTeX. Its generic
frontend dispatches complete script runs to registered backends. Egyptian
Hieroglyphs and Khitan Small Script have independent font-backed backends.
Registered SVG/PNG/JPEG/PDF assets, direct SVG and optional external providers
share one generic inline-glyph layout pipeline.
KAGE is an optional external producer, never an XSR dependency.

## Install and use

Install Python 3.11+, XeLaTeX with PGF, and a compatible static Unicode TTF/OTF:

```powershell
python -m pip install -e .
$env:TEXINPUTS = "$PWD\tex;$env:TEXINPUTS"
```

On Linux use `export TEXINPUTS="$PWD/tex:${TEXINPUTS:-}"`.

```tex
\documentclass{article}
\usepackage{xetex-stack-renderer}
\xsrEgyptianDefaultFont{fonts/MyEgyptianFont.ttf}
\begin{document}
Latin text: 𓀀𓐱𓁐. More Latin text.
{\xsrEgyptianFont{fonts/AnotherEgyptianFont.otf}𓀀𓐰𓁐}
\end{document}
```

Run `xelatex -shell-escape document.tex`. The default command establishes a
global selection; `\xsrEgyptianFont` overrides it within the current TeX group.
Neither changes the surrounding Latin font. Python and XeTeX use the **same
explicit file**, independently of ambient `fontspec` selection. Relative font
paths resolve against the XeLaTeX working directory; font-name lookup is not used.

Spaces, Unicode directories and Unicode filenames are supported. Prefer literal
forward slashes on both platforms. For native Windows backslashes in shell mode,
use the verbatim command `\xsrEgyptianFontPath{C:\Fonts\My Font.ttf}`. Paths cannot
contain `"`, `{`, `}`, `%`, `#`, `[` or `]`, NUL or line breaks. Font commands take
literal paths, not macro expressions. Paths cross the TeX/Python boundary as
Unicode codepoint lists rather than interpolated JSON strings.

## Generic inline glyphs (0.10)

An inline glyph participates in running text; it is not a figure. Register a
reasonably prepared file and use its label:

```tex
\documentclass{article}
\usepackage{xetex-stack-renderer}
\GlyphRegister{bs-042}{images/042.png}
\GlyphRegister{sign-v}{assets/sign.svg}
\begin{document}
Before \Glyph{bs-042} after. Again \Glyph{bs-042}.
Adjusted \Glyph[scale=1.2,raise=1pt]{sign-v}.
\end{document}
```

Compile with `xelatex -shell-escape document.tex`, or prepare responses once:

```console
xsr-render preprocess --input document.tex --output-dir .
xelatex -no-shell-escape document.tex
```

For the second workflow, use `\usepackage[mode=preprocess]{xetex-stack-renderer}`.
Files must remain available during final compilation. Relative asset paths are
relative to the XeLaTeX working directory (`--tex-workdir` in preprocessing,
defaulting to `--output-dir`). Use literal forward-slash paths as for direct SVG.

The registry is global and intentionally only **label -> file**. Registering
the same label with the same literal file again is harmless; a conflicting
registration fails with `XSR-GLYPH-DUPLICATE`. An unknown label fails with
`XSR-GLYPH-UNKNOWN`. Formats are inferred from the extension and verified against
the content. Aliases and provider configuration are not part of registration.

### Canvas and sizing

Supported inputs are restricted SVG, single-frame PNG, JPEG/JPG and single-page,
unencrypted PDF. The canvas is authoritative: SVG uses its design space; raster
images use pixel width/height (independent of DPI metadata); PDF uses its complete
MediaBox with page rotation applied. A PDF remains an included PDF, including
any original vector content. XSR does not convert raster images to SVG.

Prepare sensible borders yourself. XSR performs **no image processing**: no
cropping, trimming, thresholding, background removal, ink-bound analysis, OCR,
cleanup or tracing. Original image/PDF files are included without rewriting.

For intrinsic canvas `W x H`, current ideographic-cell size `C`, and uniform
use-site scale `s`, geometric-mean normalization gives:

```text
r = W / H
w = alpha * C * s * sqrt(r)
h = alpha * C * s / sqrt(r)
sqrt(w*h) = alpha * C * s
```

The policy defaults are centralized in `xsr.inline`: vector `alpha=1.00`, image
`alpha=1.10` (including PDF). The image increment accommodates common small
canvas margins. **No maximum width or height is imposed.** Tall glyphs can
expand line spacing and wide glyphs occupy additional horizontal space.
Ratios above 16:1 or below 1:16 produce `XSR-INLINE-ASPECT`, without reshaping.

The current font's positive U+3000 advance supplies `C` when available;
otherwise its em is used. U+56FD's height/depth supplies the ideographic center
when available; otherwise the reference is an em square above the baseline,
centered at `C/2`. Hosts can replace the internal cell-metrics hook. There is
no dependence on an Egyptian/Khitan font selected for a different backend.

Images first align their full canvas center to that cell center, then apply an
explicit downward optical correction to compensate for common source margins:
`shift = center - h/2 - 0.12*(C*s) + raise`. The policy bias scales with the same
ideographic unit as the glyph. PNG, JPEG and manual PDF assets share this policy;
no pixels or PDF content are inspected. Vectors start at the reference cell
baseline with zero optical bias. User `raise` remains additive and can compensate
for the default correction on any particular source.
Height and depth include the resulting extents; vector ink extending beyond its
viewBox also enlarges its reported box, without changing the normalization.

Vector side bearings are zero. Images use an explicit side bearing of `-0.02*w`
on each side, so their advance is `0.96*w`; their full canvas width remains `w`.
This small intentional overhang tightens adjacent text spacing without cropping,
clipping, reducing height/depth or hiding an oversized glyph in a fake 1em box.
The distinction lives in the shared policy layer.

Only **uniform positive finite `scale` and TeX-length `raise`** are public
adjustments. Independent width/height, xscale/yscale, stretch, crop/trim and an
aspect-preservation switch are unsupported. Font size, scale and raise are
resolved at each TeX use, so repeated occurrences share a source response even
at different sizes. Source-content changes invalidate the cached identity.

### Shared pipeline and Python primitives

Manual files, direct SVG and provider-produced SVG converge at `VisualAsset`
before `layout_inline` builds an immutable `InlineGlyph`. It carries canvas
size, full width, advance, height/depth, shift, bounds, payload and cache identity.
`inline_tex` serializes the common model; `xsr-inline.sty` resolves the current
font cell and use-site adjustments and constructs the actual TeX box.

```python
from math import isclose
from xsr.inline import GlyphRegistry, IdeographicCell, layout_inline, inline_tex

registry = GlyphRegistry(base_dir="assets")
registry.register("sample", "sample.png")
asset = registry.resolve("sample")
glyph = layout_inline(asset, IdeographicCell(size=10, center=4),
                      scale=1.2, raise_by=1)
assert isclose(glyph.canvas_width / glyph.canvas_height, asset.aspect_ratio)
tex_response = inline_tex(asset)  # current TeX font/adjustments resolved at use
```

`resolve_asset(path)` also accepts an externally acquired file;
`vector_asset(import_svg(svg_data))` adapts validated in-memory SVG geometry.
Existing provider commands remain a separate front end: users are not forced
to register generated results or place provider settings in `\GlyphRegister`.
Provider invocation and restricted SVG safety rules are unchanged.

Preprocessing executes **every literal include occurrence** under its active
brace-scoped provider/style/missing-policy state. Only the active recursion
stack detects cycles. Include lookup prefers the current parent directory,
then explicit entrypoint directories in order; previously visited directories
do not change lookup. Literal traversal is not a general TeX interpreter.

Post-0.10 maintenance keeps the public release number at 0.10 and uses internal
backend version `inline-0.10-optical-1` for the optical policy/response format;
old inline responses cannot match the new digest. See the
[maintenance record](docs/post-0.10-maintenance.md).

0.10 adds no KAGE implementation, Bai-style IDS, zi.tools or GlyphWiki
integration, IDS-to-geometry, Han-to-IDS lookup, network glyph fetching, IMPE
integration, logical/transcription metadata, ActualText, accessibility/index
semantics or PDF copy/paste handling. Identity metadata exists only for XSR's
cache. See the [four-page inline showcase](examples/inline-glyph-showcase.pdf),
its [source](examples/inline-glyph-showcase.tex), and
[release verification](docs/v0.10-verification.md).

## External vector glyphs and providers

The three layers are deliberately separate:

1. Font-backed measurement and script layout: Egyptian and Khitan.
2. Generic geometry: imported SVG and synthetic missing-glyph boxes.
3. Optional external producer invocation: a generic provider, with a thin
   KAGE-facing TeX convenience API. No stroke/component engine lives in XSR.

### Direct SVG

```tex
\usepackage[mode=shell]{xetex-stack-renderer}
\begin{document}
Before \xsrVectorGlyph{assets/my-glyph.svg} after.
\end{document}
```

Compile with `xelatex -shell-escape document.tex`. No font selection is needed
for vector-only use. Unicode filenames and spaces work; use literal forward
slashes. Relative SVG and configuration paths resolve from the **XeLaTeX working
directory**, also used by preprocess (`--tex-workdir`, default `--output-dir`).
Paths must not contain TeX reserved characters, backslashes, NUL or line breaks;
use plain filenames rather than macro expansions or TeX escaping.

The SVG design space is its `viewBox`, or numeric `width` and `height` if no
viewBox exists. The common inline pipeline uses geometric-mean normalization
with vector alpha 1.00 and preserves aspect ratio. With an em-square reference,
a 200 x 200 asset has advance 1em, height 1em, depth zero and a bottom baseline.
Ink bounds never rescale a glyph. The SVG y axis is inverted into TeX's y-up
geometry. These are glyph metrics, not browser viewport layout: when viewBox
exists it defines the design space independently of the physical viewport size.
Outlines are not clipped to the design cell. Glyph objects retain design size,
normalized source geometry, bounds, commands and affine transforms, not XML.
The shared InlineGlyph layer supplies final advance/height/depth.

Output is PGF path geometry in PDF. There is no rasterization, Inkscape,
LaTeX `svg` package, intermediate image/PDF or invented Unicode/PUA mapping.

### Restricted SVG contract

Supported UTF-8 SVG elements are `svg`, nested `g`, and `path` only. A rectangle
must be written as a path; the `rect` element is intentionally unsupported.

- Container: positive numeric/px `width` and `height`; arbitrary positive
  `viewBox` dimensions and nonzero origins; optional SVG namespace and version.
- Paths: `M/m L/l H/h V/v Q/q C/c Z/z`, repeated arguments, implicit line-to
  after move-to, decimals, signs and exponent notation. Quadratics become exact
  cubics using the two-thirds control-point conversion.
- Transforms: `translate`, `rotate` (optionally about a center), `scale` and
  six-number `matrix`, including transform lists and nested groups.
- Paint: black (`black`, `#000`, `#000000`) or `none` fill/stroke, inherited
  through groups, numeric nonnegative `stroke-width`. Default nonzero fill,
  butt caps, miter joins and miter limit 4. Canvas transforms also transform
  stroke geometry. Fill bounds use exact Bezier extrema; stroke bounds are
  conservative miter bounds. `id` is accepted as inert metadata.

Everything else is rejected with `XSR-SVG-INVALID`, including unsupported path
commands, CSS/style attributes, opacity, text, scripts, images, references,
URLs, gradients, filters, masks, clipping, animation and foreign namespaces.
DTD/entity declarations and processing instructions are rejected before the
standard-library XML parser sees them. The parser has no external resolver.
There is a 2 MB asset limit, a 64-level nesting limit, and finite-coordinate
checks. This is a glyph importer, not general SVG or a browser.

### Optional provider and KAGE frontend

Already have a KAGE-compatible environment? Supply an executable wrapper that
accepts this implementation-independent protocol:

```text
xsr-kage-provider --glyph IDENTIFIER --style serif --output /temporary/glyph.svg
```

On success, exit 0 and write valid SVG to the requested absolute output path.
Return nonzero on failure. Optional exit status 3 means the glyph was not found;
exit 0 without a nonempty SVG is also classified as missing. The producer can be
Python, Node, a compiled program, or a wrapper around any installed engine.
XSR neither installs an engine nor downloads/manages GlyphWiki datasets.

Create a local `provider.json`:

```json
{
  "executable": "xsr-kage-provider",
  "prefix_args": [],
  "metadata": {"engine_version": "your-version", "dataset_version": "your-revision"},
  "timeout": 30
}
```

Only `executable` is required. A bare executable name is searched on PATH;
a relative executable containing a slash is resolved against the configuration
file. For an interpreter-based wrapper, set `executable` to its absolute path
and `prefix_args` to an array containing the absolute wrapper path. Prefix
arguments are literal and are not shell-parsed or implicitly path-rewritten.
On Windows use an executable/interpreter, not a `.bat`/`.cmd` shell wrapper.
Configuration is trusted executable selection, not a sandbox for untrusted programs.

```tex
\xsrKageProvider{provider.json}
\xsrKageGlyph{glyphwiki-name}             % default serif
{\xsrKageStyle{sans}\xsrKageGlyph{another-name}}
```

The generic equivalents are `\xsrVectorProvider{provider.json}`,
`\xsrVectorStyle{literal-style}` and `\xsrProviderGlyph{identifier}`.
KAGE convenience commands delegate to these; they know no KAGE API.
KAGE styles are `serif` and `sans`; generic TeX styles use letters, digits,
underscores or hyphens. Literal glyph identifiers may contain Unicode. Strings
cross the request bridge as codepoints, never as interpolated shell syntax.
Python invokes `subprocess.run(argv, shell=False)` with a timeout (default
30 seconds, configurable up to 300). No shell command string or pipeline is parsed.
An optional configuration `options` object is transported as a single
`--options-json JSON` argument; omit it for the minimal three-argument protocol.
Optional engine/dataset metadata is retained without being required or guessed.

The shortest workflow is: install/configure your engine independently, provide
its wrapper and JSON configuration, request a glyph, let the wrapper emit SVG,
and let XSR import/cache/draw it. No KAGE wrapper or implementation is shipped
in the MIT runtime. The committed test producer emits original geometric
shapes only and is explicitly **not KAGE**.

### Preprocessing and cache identity

```text
python -m xsr.renderer preprocess --input document.tex --output-dir build --tex-workdir .
xelatex -no-shell-escape -output-directory=build document.tex
```

Preprocess discovers literal direct/provider/KAGE commands, follows literal
input/include files, and tracks brace-scoped provider/style/policy selections.
Each unique provider request is generated once per invocation. Responses retain
their content-addressed identities inside one document bundle; final TeX
compilation invokes no provider. Keep the local SVG/configuration
files available for their content checks. Changing either requires preprocessing
again. Arbitrary macro expansion, conditionals and dynamically assembled commands
are outside the conservative source discoverer's scope. Existing font discovery
still prepares the cross-product of discovered fonts and backend options.

Direct SVG cache identity includes normalized absolute source path, content MD5
(for the TeX bridge), authoritative content SHA-256, importer/backend version,
and rendering options. Provider identity includes executable/prefix arguments,
configuration/options/metadata, identifier, style, resulting SVG SHA-256 and
importer version. Cached SVG remains interchange and is revalidated on import;
the final response contains PGF geometry. When persistent caching is explicitly enabled, provider records retain the content
digest and metadata next to cached SVG. A result digest is never inferred from
an identifier alone.

In shell mode the first glyph calls the provider and imports SVG. Repeated
requests in the same document reuse an unexpanded in-memory response without
starting another provider. Persistent caching is disabled by default; producer
results persist across builds only with an explicit cache directory.
Provider failures are not stored as successful SVG; their typed fallback
responses can still be reused within the TeX document. Change the configuration
metadata revision or remove the provider cache when the engine/dataset changes.
The provider cannot reveal changes to its environment unless its configured
identity changes. The `obtain_many` abstraction leaves future batch invocation
open; 0.10 invokes one process per unique uncached request.

### Missing-glyph policy

```tex
\xsrMissingGlyphPolicy{box}   % default; scoped by TeX groups
\xsrMissingGlyphPolicy{error} % strict
```

Python options use `missing_glyph_policy='box'` or `'error'`. A missing visible
font glyph is replaced by a generic hollow compound vector path and emits
`XSR-GLYPH-MISSING`. Both backends use a nominal 1em square in normalized font
units; KSS centers it in the normal slot, and Egyptian H/V packing applies the
same scaling/padding as for other signs. Missing shapes are never guessed.
KSS U+16FE4/SPACE/ZWSP and Egyptian controls/variation selectors never become
tofu, because only parser-selected visible signs request glyph metrics.
An empty outline keeps its existing distinct `XSR-GLYPH-EMPTY` error.

External fallback warnings distinguish `XSR-PROVIDER-UNAVAILABLE`,
`XSR-PROVIDER-MISSING`, `XSR-PROVIDER-FAILED`, and `XSR-PROVIDER-SVG`.
Under `box`, each draws a nominal 1em placeholder; under `error`, each fails.
Malformed direct SVG always fails. Invalid provider configuration always fails.
The Python warning has a typed `XSRWarning.code`, and cached TeX responses also
log the warning. The selected font's `.notdef` or a Unicode box is never used.

See the [three-page vector/provider showcase](examples/vector-showcase.pdf),
its [source](examples/vector-showcase.tex), and [0.9 verification](docs/v0.9-verification.md).
Rebuild it with `python scripts/build_vector_showcase.py` after fetching the two
Noto reference fonts. Real KAGE is neither used nor required for the showcase or CI.

Intentional non-goals: KAGE stroke/component algorithms, GlyphWiki downloading,
IDS/Han synthesis, font-style fitting, font export, PUA mappings, vertical-flow
changes, general SVG, raster fallback, and automatic provider environment management.

## Khitan Small Script

Select an explicit static Unicode outline font. The same file supplies Python
metrics and XeTeX glyphs:

    \xsrKhitanDefaultFont{fonts/NotoSerifKhitanSmallScript-Regular.ttf}
    In text: 𘬁𘬂 𘬁𘬂.
    \xsrKhitanText{𘬁𘬂 𘬁𘬂}

The standalone detector groups consecutive KSS characters into one cluster.
U+0020 SPACE ends a cluster and inserts a visible, breakable **0.2 em** gap
between adjacent KSS clusters. U+200B ZERO WIDTH SPACE ends a cluster with a
zero-width break opportunity. Spaces next to Latin or other scripts remain
ordinary TeX spaces. The explicit command is useful when source tokenization
is controlled by another package. The gap can be scoped with
\xsrKhitanClusterGap{0.35}; Python callers use cluster_gap=0.35.

U+16FE4 KHITAN SMALL SCRIPT FILLER occurs **once, immediately after the first
sign** of a multi-sign cluster. Without it, Type A places pairs left/right
from the first row, with a final odd sign centered. With it, Type B centers
the first sign, then places the remaining signs in left/right pairs, again
centering a final odd sign. Text order is left to right, then top to bottom.
The iteration mark U+18B00 is a sign in the stack; its repetition meaning is
not drawn as a duplicate. U+18CFF is accepted as an unidentified/missing sign
with the selected outline, or a synthetic missing-glyph box when it is absent. Unassigned codepoints and malformed
filler/separators fail with typed Khitan diagnostics. Unicode describes typical
phonograms of two to eight signs, with single-sign units also possible;
the implementation does not impose a smaller arbitrary length limit.

Layout uses the selected font's actual advances and ink bounds to center each
original glyph in a fixed slot. Every glyph has scale 1: no Noto positional
alternates, discretionary ligatures, compression, rotation, or glyph-specific
coordinate tables are required. A two-column cluster is approximately two
font ems wide. It is an indivisible, upright box with natural height, bottom
aligned to the horizontal text baseline. A four-row cluster is at least four
ems high and enlarges only its containing TeX line. Full traditional vertical
document flow is reserved; the internal cluster order and geometry can be
reused by a future vertical host.

The [five-page Khitan showcase](examples/khitan-showcase.pdf) includes a
reference comparison with Noto's native rclt shaping and a fifth page comparing
the same XSR layout in Noto and the user-supplied Khitan Small Linear font. Native Noto produces
the same structural ordering in the tested corpus, with its own optical
refinements. XSR correctness never depends on that feature. The reference
font is the official [Noto Khitan release v1.000](https://github.com/notofonts/khitan-small-script/releases/tag/NotoSerifKhitanSmallScript-v1.000)
(commit c659d517071caaa442218626c6b59db52c785c76). The pinned release
archive SHA-256 is
daf885a451fe4c9446d5cbbe6c8a2415b62d92f2636cbd1bacb29da4d7475ff5;
the extracted hinted TTF SHA-256 is
ad6d20d17e7b0af746106b8e0e3ac65c47f6813a4acb6e05786023e1374a953f.
No font binary is committed. The optional Linear font file used for the
committed comparison page has SHA-256
E5DEA2755975D4BAAFA3DAF5E6A695C1338F3298B3836B07EE39FD1E61B7BC95.
The official Noto v1.000 font lacks U+18CFF. XSR 0.10 renders a synthetic
1em hollow box in its normal KSS slot and logs `XSR-GLYPH-MISSING`.
The strict `error` policy raises instead; a font with an outline uses that outline.

Unicode sources for these rules are [Unicode 18 chapter 18, section 18.12](https://www.unicode.org/versions/Unicode18.0.0/core-spec/chapter-18/),
the [Unicode 18 names list for U+18B00..U+18CFF](https://www.unicode.org/Public/18.0.0/charts/nameslist/18b00/),
and the [Khitan cluster proposal figures](https://www.unicode.org/L2/L2018/18121r-n4943-khitan-cluster.pdf).
The current Unicode chapter defines U+16FE4 as the Type B marker; older
proposal examples using CGJ are not the 0.8 syntax.

## EHFC support

The accepted syntax follows Unicode 18 Egyptian format controls. XSR parses EHFC natively.
Start/end are logical: left/right in LTR, right/left in RTL.

| Feature | Controls / support in 0.7 |
| --- | --- |
| Plain signs | Unicode glyphs present in the selected font |
| Vertical / horizontal | U+13430 / U+13431; nested groups |
| Segments | U+13437 / U+13438, with recursive grouping |
| Corner insertion | U+13432–U+13435: top-start, bottom-start, top-end, bottom-end |
| Middle / top / bottom insertion | U+13439 / U+1343A / U+1343B |
| Overlay | U+13436; ink-centered horizontal and vertical arms |
| Plain enclosure | U+1343C / U+1343D; cartouche and rectangular forms |
| Walled enclosure | U+1343E / U+1343F |
| Mirror | U+13440, applied after rotation |
| Rotation | Registered sign + VS pairs from Unicode 18 StandardizedVariants; no universal VS-to-angle mapping |
| Blanks | U+13441 / U+13442: full / half |
| Lost signs | U+13443–U+13446: full, half, tall, wide; FE00 expands shading continuously |
| Damage | U+13447–U+13455: all 15 quadrant combinations, including enclosure ends |
| Editorial brackets | `[ ]`, `{ }`, U+2E22/23, U+27E8/9, U+27E6/7 in explicit Egyptian context |
| Horizontal direction | LTR and RTL; logical start/end, glyph orientation and quadrat order |
| Paragraph wrapping | TeX breaks only between top-level quadrats |
| Vertical text flow | Reserved API, explicitly unsupported; V JOINER inside quadrats is supported |

Common enclosure caps are U+13379/U+1337A (cartouche), U+13258/U+1325B
(rectangular), and U+13286/U+13287 (walled). Omitted caps leave that side open;
damage modifiers shade the corresponding cap quarters. Empty enclosures reserve a
blank quadrat. Additional plain endpoints U+13259, U+1325A, U+1325C, U+1325D,
U+13282, U+1337B and U+1342F, and walled endpoints U+13288/U+13289, use the
selected font's measured outlines with vector connecting rails. The font must
contain these less common endpoints. Mixing plain and walled endpoint families,
or mismatching the begin/end controls, is an error.

### Direction, line breaking and editorial context

```tex
{\xsrEgyptianDirection{rtl}𓀀𓁐𓅓}
\xsrEgyptianText{[𓀀𓐱𓁐]}
\xsrEgyptianText{{𓀀}} % literal editorial braces inside the argument
```

`\xsrEgyptianDirection{ltr|rtl}` is scoped, with LTR the default. Python options
use `direction='ltr'|'rtl'` and `writing_mode='horizontal'`. The reserved TeX
command `\xsrEgyptianWritingMode{vertical}` and Python vertical mode fail with
`XSR-WRITING-MODE-UNSUPPORTED`; neither rotates a whole text box to simulate
vertical writing. V JOINER remains ordinary composition within a quadrat.

RTL reverses horizontal child order and logical insertion sides, and orients glyphs
toward the reading start. Rotation is clockwise in LTR and counterclockwise relative
to the RTL-oriented glyph. Explicit mirror is applied after rotation, independently
of direction. XeTeX's direction nodes arrange logical quadrats on each output line;
XSR does not reverse an entire paragraph before line breaking.

Each quadrat is an indivisible box, separated by a zero-width legal break. TeX's
ordinary paragraph builder chooses breaks. Existing ink padding supplies spacing;
no additional inter-quadrat space is inserted. An oversized single quadrat can
still exceed the line width. An enclosing TeX `\hbox`, `\mbox` or framed sample
naturally prevents wrapping.

`\xsrEgyptianText{...}` establishes explicit Egyptian context for editorial
punctuation, including unbalanced brackets and brackets inside H/V structure.
The argument contains literal Unicode, not TeX macros. Its inner literal braces
are editorial characters; literal braces must still balance as a TeX argument.
Hosts can dispatch unbalanced curly marks as catcode-12 characters directly.
This host-dispatch API avoids globally activating ASCII
punctuation or changing TeX grouping. Outside this command, ordinary brackets and
braces retain their usual TeX meaning. Vector brackets do not require punctuation
glyphs in the Egyptian font. Consecutive nested editorial brackets are preserved;
redundant singleton segments produce equivalent native structures.

### Unicode semantics

Rotation is looked up by **base sign and selector**. For example, FE03 means
30 degrees for A15, 25 for H6, 40 for F44, and 15 for Aa11. Approximate angles in
Unicode data use their stated representative value. Unregistered pairs, including
otherwise plausible 90-degree rotations, produce `XSR-VARIANT-UNREGISTERED`.
This intentionally corrects the permissive but incorrect 0.5 behavior.

Unikemet `kEH_NoMirror=Y` prohibits an explicit U+13440 when it would change sign
identity (`XSR-NO-MIRROR`); ordinary RTL orientation remains independent.
`kEH_NoRotate=Y` rejects unregistered rotations with `XSR-NO-ROTATE`. A specific
registered variation sequence takes precedence over that broad property: Unicode
18 lists both for M003 and V006. No speculative warnings are based on provisional
catalog classifications, and legacy codepoints are not rewritten automatically.

The tables are generated from checksum-pinned Unicode **18.0.0** data. Their
rotation, NoMirror and NoRotate entries are unchanged from 17.0.0; only the
recorded Unicode version changed. To reproduce/verify them:

```powershell
python scripts/generate_unicode_data.py
python scripts/generate_unicode_data.py --check
```

The script downloads source data into ignored `tmp/unicode` if needed; the compact
generated module and Unicode license are committed and included in the package.
CI checks regeneration deterministically. Sources:
[StandardizedVariants.txt](https://www.unicode.org/Public/18.0.0/ucd/StandardizedVariants.txt),
[Unikemet.txt](https://www.unicode.org/Public/18.0.0/ucd/Unikemet.txt),
[UAX #57 revision 6](https://www.unicode.org/reports/tr57/tr57-6.html),
and [Unicode 18 chapter 11](https://www.unicode.org/versions/Unicode18.0.0/core-spec/chapter-11/).

## Font-aware architecture

```
EHFC -> native XSR parser -> immutable XSR structure
     -> selected font's outlines -> XSR layout -> same-file XeTeX glyphs + PGF
```

The parser is an independent recursive-descent implementation of Unicode
chapter 11.4.2, producing the existing `ParsedEgyptianRun` and `EgyptianNode`
model. Insertion binds before overlay, horizontal join, then vertical join.
Segments group recursively; H/V joins collect operands in source order, while
adjacent complete expressions begin separate quadrats. Modifiers attach to one sign in
variation-selector, mirror, damage order. Enclosure controls scope their
interior and optional endpoint signs. Editorial brackets attach to adjacent
horizontal content in explicit Egyptian context. The parser was built from
Unicode specifications and XSR's own semantic model, not from Hieropy source.
No external parser or reference-font measurements enter layout.
`FontMetrics`
uses fontTools for normalized metrics, decomposed outlines and exact Bezier bounds.
No font-name branches or per-font insertion coordinates are used.

H/V groups pack actual ink boxes with a 0.08 em gap. A top-level group shrinks
uniformly to at most 1 em high, never enlarges, and receives 0.04 em outer padding.
Expanded lost signs fill their allocated cross-axis cell and omit their own half
of the adjoining gap, so adjacent expanded shading has no intervening whitespace.
The baseline is the bottom of the layout box; widths need not be square.
Insertion flattens the selected outlines into a nonzero-winding occupancy mask,
including holes, reserves a margin and previous insertions, then searches the
semantic region for a fitting child rectangle. Scaling is bounded; lack of usable
space raises `XSR-INSERTION-NO-SPACE`. Overlay centers ink bounds and preserves
proportions. Transform bounds use transformed outlines. Enclosures and shading are
XSR-owned vector paths; final signs remain native font glyphs, not raster images.

Normal compatible Unicode Egyptian outline fonts should work without per-font
layout code. Unusual proportions or crowded insertion sequences may need future
tuning. Occupancy sampling is conservative but is not a proof of arbitrary-font
optical perfection.

- `src/xsr/font_metrics.py`, `ink.py`: font profiles and outline geometry.
- `src/xsr/egyptian/`: parser boundary, immutable model, layout and serialization.
- `tex/xsr-egyptian.sty`: font selection and native glyph/vector drawing.
- `tex/xsr-core.sty`, `src/xsr/renderer.py`, `cache.py`: script-neutral protocol,
  dispatch and content-addressed cache.
- `tex/xsr-detector-active.sty`: replaceable active-character detector. A generic
  contextual suffix registration keeps rotation selectors in Egyptian runs.

Hosts may omit the detector, load `xsr-core` and `xsr-egyptian`, and call
`\xsr_dispatch_run:nn{egyptian}{...}` with a complete run. The generic registry and detector now support contextual infix separators.
Direction, semantic validation and editorial context remain in the Egyptian backend.

Font contents are fingerprinted in request/cache identities and checked when TeX
loads a response. Python callers can supply `{'font_path': '/absolute/font.ttf'}`;
the backend canonicalizes options before cache lookup. MD5 is a cache fingerprint,
not an authenticity mechanism.

## Preprocess without shell escape

Use `\usepackage[mode=preprocess]{xetex-stack-renderer}` and literal default/local
font commands in the source:

```powershell
python -m xsr.renderer preprocess --input document.tex --output-dir . --tex-workdir .
xelatex -no-shell-escape document.tex
```

Ordinary preprocessing writes only two XSR files beneath the output directory:

```text
.xsr/
    document.responses.tex
    document.manifest.json
```

The bundle contains one unexpanded response body per unique request digest.
It is rewritten atomically with deterministic digest ordering on every successful
preprocess invocation; removed/changed requests do not accumulate old entries.
The manifest records each logical run, its digest key and the common bundle path.
No per-request response files, `.req` files or `.xsr-cache` are created.
Keep the bundle for repeated no-shell builds; delete `.xsr/` when no longer needed.
The TeX core loads it once and evaluates each response at use time, so current
font metrics, `scale` and `raise` remain local to each occurrence. Missing bundles
and missing keys produce `XSR-BUNDLE-MISSING` and `XSR-RESPONSE-MISSING` respectively;
malformed bodies retain `XSR-RESPONSE` validation.

Python `default_renderer()` / `Renderer(cache=None)` and provider acquisition are
cacheless by default. Provider output uses temporary storage which is removed
when acquisition completes, plus in-memory reuse during one invocation. Opt in
to persistent caching with `--cache-dir PATH` (Python preprocess/render CLI) or
`cache-dir=PATH` (TeX shell mode). Explicit provider caches retain their existing
SVG revalidation and revision-metadata rules.

Shell/auto fallback on TeX Live 2024+ honors -output-directory by using
TEXMF_OUTPUT_DIRECTORY for shell-escape request/response paths, error
responses and cleanup. Other distributions must export this variable
explicitly or use the preprocessing workflow. XSR remains version 0.10.

Shell/auto fallback uses one fixed `<job>.xsr-request.req` / `<job>.xsr-response.tex`
scratch pair, not one pair per digest. Python consumes each request; successful
TeX builds remove the remaining scratch pair at document end. A failed/interrupted
build may retain the scratch response for diagnosis. Auto mode first tries a
matching bundled response, then shell execution if allowed. No new shell escape
permission, pipes or shell-specific cleanup command is required.

When migrating a 0.10 document directory, obsolete `<job>.xsr-<hash>.tex`, the old
`<job>.xsr-manifest.json`, and an unwanted `.xsr-cache/` may be removed manually.
The new workflow ignores those old responses and does not delete existing files
that may be shared with another build.

The preprocessor recursively follows literal `\input{file}` and `\include{file}`,
appending `.tex` when needed. It searches the containing source directory first,
then the explicit input-root directories in order. Cycles and missing files are errors. Repeat `--input` for multiple
roots and `--font` for additional absolute font selections. `--tex-workdir` defaults
to the output directory and controls resolution of discovered relative font paths.
`--jobname` must match XeLaTeX when overriding its normal job name.

Literal `\xsrEgyptianText` arguments are discovered with balanced TeX argument
braces. If direction commands occur in the sources, both LTR and RTL responses
are prepared. Each distinct run is prepared for every discovered or explicit font; repeated runs
share responses. Literal path spellings are retained for TeX request identity. Khitan font selections and cluster-gap settings are prepared separately from Egyptian profiles.
This deliberately scans source, not TeX execution: it does not expand macros,
interpret conditionals, follow unbraced/computed input names, or discover the
verbatim `\xsrEgyptianFontPath` command. Use forward-slash font commands for automatic
discovery. All supplied fonts must cover every discovered run. Comments are removed;
macro bodies can still contribute runs. Regenerate after changing sources or fonts.

## Diagnostics

| Code | Meaning / action |
| --- | --- |
| `XSR-FONT-NOT-SELECTED` | Set an Egyptian default/local font |
| `XSR-FONT-MISSING` | File missing or unreadable; check the working directory |
| `XSR-FONT-FORMAT` | Use a supported static TTF/OTF |
| `XSR-GLYPH-MISSING`, `XSR-GLYPH-EMPTY` | Required codepoint has no usable outline |
| `XSR-VARIANT-UNREGISTERED` | Sign + selector is not registered in the pinned Unicode data |
| `XSR-NO-MIRROR`, `XSR-NO-ROTATE` | Identity-changing transform; use the encoded sign or registered variant |
| `XSR-DIRECTION`, `XSR-WRITING-MODE-UNSUPPORTED` | Invalid direction or reserved full vertical flow |
| `XSR-PARSE` | Invalid or parser-unsupported syntax; includes codepoints |
| `XSR-UNSUPPORTED` | Recognized feature not implemented |
| `XSR-INSERTION-NO-SPACE` | No safe region at the supported minimum scale |
| `XSR-STALE` | Font or external asset content changed; regenerate preprocessed output |
| `XSR-INVOCATION` | Python renderer failed to produce a response |
| `XSR-REQUEST`, `XSR-RESPONSE` | Malformed protocol input/output |
| `XSR-PREPROCESS`, `XSR-SOURCE-MISSING` | Source discovery failed |

Shell mode overwrites the response with an error sentinel before invoking Python,
so an unsuccessful invocation cannot silently reuse an earlier successful response.

## Verification and showcase

```powershell
python -m pip install '.[test]'
python scripts/fetch_noto.py
python scripts/fetch_newgardiner.py
python scripts/fetch_khitan.py
python -m pytest
python -m pytest tests/test_tex_integration.py tests/test_khitan_tex.py tests/test_vector_tex.py tests/test_inline_tex.py tests/test_bundles.py
python scripts/build_showcase.py --font tmp/fonts/NotoSansEgyptianHieroglyphs-Regular.ttf --font tmp/fonts/NewGardiner.ttf --font C:/Windows/Fonts/seguihis.ttf
python scripts/check_showcase.py examples/egyptian-showcase.pdf
python scripts/build_khitan_showcase.py --font tmp/fonts/NotoSerifKhitanSmallScript-Regular.ttf --comparison-font D:/_INBOX/Download/KhitanSmallLinear.ttf
python scripts/check_khitan_showcase.py examples/khitan-showcase.pdf
python scripts/build_vector_showcase.py
python scripts/check_vector_showcase.py examples/vector-showcase.pdf
python scripts/build_inline_showcase.py
python scripts/check_inline_showcase.py examples/inline-glyph-showcase.pdf
```

The builder accepts two or three fonts and compiles in a fresh temporary directory
without shell escape. The committed [six-page 0.10 showcase](examples/egyptian-showcase.pdf)
and [editable source](examples/egyptian-showcase.tex) compare Noto, NewGardiner and
Segoe UI Historic across basic layout, all seven insertion slots, overlay,
enclosures, registered transforms, RTL, editorial brackets, continuous shading,
paragraph wrapping and combinations. The older
[font-metrics showcase](examples/font-metrics-showcase.pdf) preserves the historical 0.4 corpus, rebuilt with 0.9.

[GitHub Actions](.github/workflows/ci.yml) installs the package on Ubuntu 24.04 with
Python 3.11, focused TeX Live packages and Poppler; downloads checksum-verified Noto Egyptian, NewGardiner and Noto Khitan
from their official repositories at runtime; verifies Hieropy is absent, runs
all tests plus separate XeLaTeX integration, and rebuilds all four current showcases. Test reports, PDF and page images are artifacts, never automatic
commits. NewGardiner is fetched from its pinned official upstream revision; Segoe is
optional on Windows. No external fonts are vendored. Noto can also be selected with `XSR_NOTO_FONT`; additional test
fonts use `XSR_TEST_FONTS` (an `os.pathsep`-separated list).

See [0.7 verification](docs/v0.7-verification.md). The
[0.6 verification and unsupported-case audit](docs/v0.6-verification.md) is historical.
The [0.5 verification](docs/v0.5-verification.md) and
[0.4 verification](docs/v0.4-verification.md) are historical records.

## Remaining limits

- Static TrueType fonts have the broadest verification. Static CFF outlines are
  supported through fontTools; variable fonts, collections, webfonts and color-only
  glyphs are unsupported. Signs require a Unicode cmap entry and nonempty outline.
- Full vertical text flow, advanced baseline alignment and HieroTeX compatibility
  remain deferred. Deep nesting can make signs small; individual large quadrats
  cannot be split across lines.
- Native Unicode-based parsing rejects malformed joiners, unknown controls and
  invalid enclosure combinations with typed errors.
- NewGardiner lacks U+0020 and can cause a harmless loading warning; Latin labels
  use the document font and XSR emits only selected Egyptian glyphs.
- The standalone detector changes registered character catcodes. Hosts with different
  tokenization requirements should use the generic dispatch API.

- Contextual OpenType alternates remain optional future work. GSUB feature names do
  not identify insertion cavities or provide a generic safe alternate-selection
  rule. XSR therefore keeps `XSR-INSERTION-NO-SPACE` instead of guessing substitutes.
  The tested Noto/NewGardiner files contain no GSUB tables; Segoe's other-script
  features are not Egyptian insertion metadata.
- A cmap entry can still point to a font-supplied placeholder drawing. XSR cannot
  generally distinguish such a drawing from an intentional geometric sign; visual
  review and a suitable font remain necessary.

## Dependencies and licenses

XSR source is [MIT licensed](LICENSE). Its direct runtime dependencies are
[fontTools](https://github.com/fonttools/fonttools) (MIT) for outline geometry,
[Pillow](https://github.com/python-pillow/Pillow) (MIT-CMU) for existing font ink
masks and image header metadata, and
[pypdf](https://github.com/py-pdf/pypdf/blob/main/LICENSE) (BSD-3-Clause) for PDF
page metadata. pypdf is a pure-Python reader; inline assets use metadata only,
without a PDF rendering dependency or image-processing pass.
Hieropy is not a runtime or test dependency. Generated Unicode semantics retain
the [Unicode data license](src/xsr/egyptian/unicode-LICENSE.txt) in the wheel.
Noto Sans Egyptian Hieroglyphs (SIL OFL 1.1) and NewGardiner (SIL OFL 1.1)
are external test inputs downloaded with pinned SHA-256 checksums; no font is
bundled with XSR. Segoe UI Historic is an optional local Windows test font.
