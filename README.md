# xetex-stack-renderer

XSR 0.4.0 is a Unicode-driven stack renderer for XeTeX/XeLaTeX. The standalone
frontend detects complete script runs and dispatches them to registered backends.
Egyptian Hieroglyphs is the first backend.

## Font-aware Egyptian rendering

The pipeline is:

```
EHFC Unicode -> Hieropy parser -> immutable XSR structure
             -> selected font's outline metrics -> XSR H/V layout
             -> XeTeX glyphs from that same font file
```

Hieropy 0.1.4 supplies **syntax and structure only**. XSR does not call its
`format`, `fit`, `size`, rasterization or NewGardiner measurement routines.
Noto Sans Egyptian Hieroglyphs and NewGardiner are reference/test fonts, not
required layout fonts. Segoe UI Historic has also been tested. There are no
font-name branches or per-font geometry overrides.

`FontMetrics` reads static TTF/OTF files with
[fontTools](https://fonttools.readthedocs.io/en/latest/ttLib/ttFont.html).
It exposes units per em, normalized advance, exact outline bounds, ink width
and height, ascender/descender/line gap, and decomposed em-normalized outline
recordings. Bounds include Bezier extrema and composites. Font parsing stays
in `src/xsr/font_metrics.py`; Egyptian layout uses only that abstraction.

H groups pack left to right; V groups pack top to bottom. Children retain their
natural proportions and are centered on the other axis. Gaps are 0.08 em before
fitting. Each top-level group shrinks uniformly, if needed, to at most 1 em high;
it is never enlarged. Outer padding is 0.04 em. Width is not constrained to a
square. The inline baseline is the bottom of the layout box. XeTeX places raw
Unicode-mapped glyphs using the measured left bearing and yMax, avoiding both
ambient-font substitution and shaping-dependent geometry changes.

## Use

```powershell
python -m pip install -e .
$env:TEXINPUTS = "$PWD\tex;$env:TEXINPUTS"
```

Select a **local static font file explicitly**, independently of the Latin font:

```tex
\documentclass{article}
\usepackage{xetex-stack-renderer}
\xsrEgyptianFont{C:/Fonts/MyEgyptianFont.ttf}
\begin{document}
Latin text: 𓀀𓐱𓁐. More Latin text.
{\xsrEgyptianFont{C:/Fonts/AnotherEgyptianFont.otf}𓀀𓐰𓁐}
\end{document}
```

Run `xelatex -shell-escape document.tex`. Font selection is scoped to TeX
groups and does not change the surrounding text font. It is a deliberate v0.4
API change: selecting an ambient `fontspec` family alone is no longer enough.
A missing font, missing sign, empty outline, or unsupported construct fails
explicitly; there is no fallback to NewGardiner metrics.

Use literal paths with forward slashes and ASCII letters/digits, spaces,
underscores, dots, colons and hyphens. Paths containing TeX/JSON metacharacters
or non-ASCII characters are currently rejected by the bridge. Spaces are
supported. Relative paths resolve against the XeLaTeX working directory.

The file's content digest is part of each TeX request/cache identity and is
checked again when a response selects the font. Python callers may pass
`{'font_path': '/absolute/font.ttf'}`; the backend adds a fresh digest before
cache lookup. A supplied stale `font_digest` is rejected. MD5 here is a cache
fingerprint, not a security or authenticity check.

### Without shell escape

Use `\usepackage[mode=preprocess]{xetex-stack-renderer}` and an **absolute font
path** in the source. Pass the same file to the preprocessor:

```powershell
python -m xsr.renderer preprocess --input document.tex --output-dir . --font C:/Fonts/MyEgyptianFont.ttf
xelatex -no-shell-escape document.tex
```

The CLI canonicalizes `--font` to an absolute path, so TeX must use that identical
path spelling for matching response identities. The simple preprocessor scans
raw Unicode runs, not TeX expansion or `\input`. It prepares one selected font
per invocation; run it once for each font used by a multi-font document. The
showcase builder demonstrates this without requiring shell escape.

## Architecture

- `tex/xsr-core.sty`: generic backend registry, run dispatch, request/response
  protocol, and invocation modes. Its behavior is unchanged in v0.4.
- `tex/xsr-detector-active.sty`: replaceable standalone active-character detector.
- `tex/xsr-egyptian.sty`: Egyptian file selection, request options, exact-file
  glyph selection and ink placement.
- `src/xsr/egyptian/hieropy_adapter.py`: parser boundary; rejects unsupported
  nodes and converts accepted nodes to an XSR-owned tree.
- `src/xsr/egyptian/layout.py`: font-agnostic H/V packing, with no Hieropy imports.
- `src/xsr/egyptian/model.py`: immutable tree and em-based geometry.
- `src/xsr/egyptian/backend.py`: font validation and XeTeX serialization.
- `src/xsr/renderer.py`, `cache.py`: generic renderer and content-addressed cache.
  An optional backend option-preparation hook validates external inputs before
  cache lookup; this prevents stale file-dependent results without script logic
  in the generic renderer.

Hosts can omit the active detector, load `xsr-core` and `xsr-egyptian`, then call
`\xsr_dispatch_run:nn{egyptian}{...}` with a complete run.

## Tests and visual comparison

```powershell
python -m pytest
python -m pytest tests/test_tex_integration.py
```

NewGardiner is located in the installed Hieropy package. Noto is discovered at
`tmp/fonts/NotoSansEgyptianHieroglyphs-Regular.ttf`, or via `XSR_NOTO_FONT`.
It can be obtained from the open-source
[Noto font repository](https://github.com/notofonts/noto-fonts/tree/main/hinted/ttf/NotoSansEgyptianHieroglyphs).
Segoe UI Historic is discovered in Windows Fonts when available. Additional
local fonts can be supplied using `XSR_TEST_FONTS` (an `os.pathsep`-separated
list). Font files are not vendored. Synthetic test fonts independently check
normalization, nonzero bearings, descenders and cache invalidation.

The committed [two-page visual showcase](examples/font-metrics-showcase.pdf)
compares identical single, H, V and nested H/V sequences in three fonts, with
Latin labels and framed layout extents. Rebuild it with any three compatible
fonts:

```powershell
python scripts/build_showcase.py --font C:/Fonts/NotoSansEgyptianHieroglyphs-Regular.ttf --font C:/Fonts/NewGardiner.ttf --font C:/Windows/Fonts/seguihis.ttf
```

The editable source is `examples/font-metrics-showcase.tex`. The builder writes
local font configuration and preprocessed responses under `tmp/pdfs/showcase`,
compiles without shell escape, and retains the final PDF in `examples/`.
See [v0.4 verification](docs/v0.4-verification.md) for baseline and final results.

## Current limits

- Only plain signs, horizontal U+13431, vertical U+13430, and parser-supported
  nested H/V segments are implemented. Insertion, overlay, enclosure/cartouche,
  damage/shading, mirror and rotation remain unsupported.
- Tested with three static TrueType fonts, not every Egyptian font. Static CFF
  OpenType outlines are handled by fontTools; collections, variable instances,
  webfonts and color-only glyphs are not supported. Required signs must exist
  in the selected font's Unicode cmap and have nonempty outlines.
- Packing uses rectangular ink bounds, not optical fitting or insertion zones.
  Deep nesting can make signs small; long horizontal runs can exceed line width.
  No line breaking, RTL layout or advanced baseline alignment is provided.
- Hieropy's grammar still determines accepted syntax. Redundant segment controls
  are not always accepted. Its installed dependencies remain required even
  though its measurement font is not used by XSR layout.
- NewGardiner has no U+0020 glyph; XeTeX can warn about this while loading the
  font. XSR emits only sign glyphs from it; Latin labels use the document font.
- The standalone detector changes character catcodes for registered ranges.
  Hosts needing different detection should use the generic dispatch API.
- No HieroTeX compatibility.
