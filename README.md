# xetex-stack-renderer

XSR **0.5** is a Unicode-driven stack renderer for XeTeX/XeLaTeX. Its generic
frontend dispatches complete script runs to registered backends. Egyptian
Hieroglyphs is the first backend.

## Install and use

Install Python 3.11+, XeLaTeX with PGF, and a compatible static Egyptian TTF/OTF:

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

## EHFC support

The accepted syntax follows Hieropy 0.1.4 and Unicode Egyptian format controls.
Start/end refer to left/right in the supported left-to-right layout.

| Feature | Controls / support in 0.5 |
| --- | --- |
| Plain signs | Unicode glyphs present in the selected font |
| Vertical / horizontal | U+13430 / U+13431; nested groups |
| Segments | U+13437 / U+13438, where accepted by the parser |
| Corner insertion | U+13432–U+13435: top-start, bottom-start, top-end, bottom-end |
| Middle / top / bottom insertion | U+13439 / U+1343A / U+1343B |
| Overlay | U+13436; ink-centered horizontal and vertical arms |
| Plain enclosure | U+1343C / U+1343D; cartouche and rectangular forms |
| Walled enclosure | U+1343E / U+1343F |
| Mirror | U+13440, applied after rotation |
| Rotation | FE00–FE06: clockwise 90, 180, 270, 45, 135, 225, 315 degrees |
| Blanks | U+13441 / U+13442: full / half |
| Lost signs | U+13443–U+13446: full, half, tall, wide; diagonal shading |
| Damage | U+13447–U+13455: all 15 quadrant combinations; diagonal shading |

Common enclosure caps are U+13379/U+1337A (cartouche), U+13258/U+1325B
(rectangular), and U+13286/U+13287 (walled). Omitted caps leave that side open.
Other cap combinations, damaged caps, empty enclosures and continuous lost-sign
shading (`lost sign + variation selector`) fail explicitly. This is substantial
practical EHFC coverage, not a claim to implement every parser production.

## Font-aware architecture

```
EHFC -> Hieropy syntax -> immutable XSR structure
     -> selected font's outlines -> XSR layout -> same-file XeTeX glyphs + PGF
```

Hieropy supplies parsing and structure only. Its `format`, `fit`, `size`, alternate
glyph recipes and NewGardiner measurements are not layout inputs. `FontMetrics`
uses fontTools for normalized metrics, decomposed outlines and exact Bezier bounds.
No font-name branches or per-font insertion coordinates are used.

H/V groups pack actual ink boxes with a 0.08 em gap. A top-level group shrinks
uniformly to at most 1 em high, never enlarges, and receives 0.04 em outer padding.
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
`\xsr_dispatch_run:nn{egyptian}{...}` with a complete run. Core changes in 0.5 are
limited to diagnostics, response validation and a failed-invocation sentinel;
Egyptian concepts remain in the backend.

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

The preprocessor recursively follows literal `\input{file}` and `\include{file}`,
appending `.tex` when needed. It searches input-root directories, then the containing
source directory. Cycles and missing files are errors. Repeat `--input` for multiple
roots and `--font` for additional absolute font selections. `--tex-workdir` defaults
to the output directory and controls resolution of discovered relative font paths.
`--jobname` must match XeLaTeX when overriding its normal job name.

Each distinct run is prepared for every discovered or explicit font; repeated runs
share responses. Literal path spellings are retained for TeX request identity.
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
| `XSR-PARSE` | Invalid or parser-unsupported syntax; includes codepoints |
| `XSR-UNSUPPORTED` | Recognized feature not implemented |
| `XSR-INSERTION-NO-SPACE` | No safe region at the supported minimum scale |
| `XSR-STALE` | Font content changed; regenerate preprocessed output |
| `XSR-INVOCATION` | Python renderer failed to produce a response |
| `XSR-REQUEST`, `XSR-RESPONSE` | Malformed protocol input/output |
| `XSR-PREPROCESS`, `XSR-SOURCE-MISSING` | Source discovery failed |

Shell mode overwrites the response with an error sentinel before invoking Python,
so an unsuccessful invocation cannot silently reuse an earlier successful response.

## Verification and showcase

```powershell
python -m pip install '.[test]'
python scripts/fetch_noto.py
python -m pytest
python -m pytest tests/test_tex_integration.py
python scripts/build_showcase.py --font tmp/fonts/NotoSansEgyptianHieroglyphs-Regular.ttf --font C:/Fonts/NewGardiner.ttf --font C:/Windows/Fonts/seguihis.ttf
python scripts/check_showcase.py examples/egyptian-showcase.pdf
```

The builder accepts two or three fonts and compiles in a fresh temporary directory
without shell escape. The committed [four-page 0.5 showcase](examples/egyptian-showcase.pdf)
and [editable source](examples/egyptian-showcase.tex) compare Noto, NewGardiner and
Segoe UI Historic across basic layout, all seven insertion slots, overlay,
enclosures, transforms, shading and combinations. The older
[font-metrics showcase](examples/font-metrics-showcase.pdf) is the historical 0.4 baseline.

[GitHub Actions](.github/workflows/ci.yml) installs the package on Ubuntu 24.04 with
Python 3.11, focused TeX Live packages and Poppler; downloads checksum-verified Noto
from the official Noto repository at runtime; runs all tests; and rebuilds a
two-font showcase. Test reports, PDF and page images are artifacts, never automatic
commits. NewGardiner comes from Hieropy; Segoe is optional on Windows. No external
fonts are vendored. Noto can also be selected with `XSR_NOTO_FONT`; additional test
fonts use `XSR_TEST_FONTS` (an `os.pathsep`-separated list).

See [0.5 verification](docs/v0.5-verification.md) and the historical
[0.4 verification](docs/v0.4-verification.md).

## Remaining limits

- Static TrueType fonts have the broadest verification. Static CFF outlines are
  supported through fontTools; variable fonts, collections, webfonts and color-only
  glyphs are unsupported. Signs require a Unicode cmap entry and nonempty outline.
- No RTL layout, line breaking, advanced baseline alignment or HieroTeX compatibility.
  Deep nesting can make signs small and long horizontal runs can exceed line width.
- Hieropy's grammar determines accepted structure, including segment restrictions.
  Its dependency packages remain installed even though its layout is not used.
- NewGardiner lacks U+0020 and can cause a harmless loading warning; Latin labels
  use the document font and XSR emits only selected Egyptian glyphs.
- The standalone detector changes registered character catcodes. Hosts with different
  tokenization requirements should use the generic dispatch API.
