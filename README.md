# xetex-stack-renderer

XSR **0.6** is a Unicode-driven stack renderer for XeTeX/XeLaTeX. Its generic
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
Start/end are logical: left/right in LTR, right/left in RTL.

| Feature | Controls / support in 0.6 |
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
| Rotation | Registered sign + VS pairs from Unicode 17 StandardizedVariants; no universal VS-to-angle mapping |
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
redundant singleton segments are normalized before structural parsing.

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
17 lists both for M003 and V006. No speculative warnings are based on provisional
catalog classifications, and legacy codepoints are not rewritten automatically.

The tables are generated from checksum-pinned Unicode **17.0.0** data, the stable
release selected for this implementation, rather than the proposed Unicode 18
update. To reproduce/verify them:

```powershell
python scripts/generate_unicode_data.py
python scripts/generate_unicode_data.py --check
```

The script downloads source data into ignored `tmp/unicode` if needed; the compact
generated module and Unicode license are committed and included in the package.
CI checks regeneration deterministically. Source specifications:
[StandardizedVariants.txt](https://www.unicode.org/Public/17.0.0/ucd/StandardizedVariants.txt),
[Unikemet.txt](https://www.unicode.org/Public/17.0.0/ucd/Unikemet.txt),
[UAX #57 revision 5](https://www.unicode.org/reports/tr57/tr57-5.html),
and [Unicode 17 chapter 11](https://www.unicode.org/versions/Unicode17.0.0/core-spec/chapter-11/).

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
`\xsr_dispatch_run:nn{egyptian}{...}` with a complete run. The generic core and detector are unchanged in 0.6 apart from version metadata.
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

The preprocessor recursively follows literal `\input{file}` and `\include{file}`,
appending `.tex` when needed. It searches input-root directories, then the containing
source directory. Cycles and missing files are errors. Repeat `--input` for multiple
roots and `--font` for additional absolute font selections. `--tex-workdir` defaults
to the output directory and controls resolution of discovered relative font paths.
`--jobname` must match XeLaTeX when overriding its normal job name.

Literal `\xsrEgyptianText` arguments are discovered with balanced TeX argument
braces. If direction commands occur in the sources, both LTR and RTL responses
are prepared. Each distinct run is prepared for every discovered or explicit font; repeated runs
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
| `XSR-VARIANT-UNREGISTERED` | Sign + selector is not registered in the pinned Unicode data |
| `XSR-NO-MIRROR`, `XSR-NO-ROTATE` | Identity-changing transform; use the encoded sign or registered variant |
| `XSR-DIRECTION`, `XSR-WRITING-MODE-UNSUPPORTED` | Invalid direction or reserved full vertical flow |
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
without shell escape. The committed [six-page 0.6 showcase](examples/egyptian-showcase.pdf)
and [editable source](examples/egyptian-showcase.tex) compare Noto, NewGardiner and
Segoe UI Historic across basic layout, all seven insertion slots, overlay,
enclosures, registered transforms, RTL, editorial brackets, continuous shading,
paragraph wrapping and combinations. The older
[font-metrics showcase](examples/font-metrics-showcase.pdf) is the historical 0.4 baseline.

[GitHub Actions](.github/workflows/ci.yml) installs the package on Ubuntu 24.04 with
Python 3.11, focused TeX Live packages and Poppler; downloads checksum-verified Noto
from the official Noto repository at runtime; runs all tests; and rebuilds a
two-font showcase. Test reports, PDF and page images are artifacts, never automatic
commits. NewGardiner comes from Hieropy; Segoe is optional on Windows. No external
fonts are vendored. Noto can also be selected with `XSR_NOTO_FONT`; additional test
fonts use `XSR_TEST_FONTS` (an `os.pathsep`-separated list).

See [0.6 verification and unsupported-case audit](docs/v0.6-verification.md).
The [0.5 verification](docs/v0.5-verification.md) and
[0.4 verification](docs/v0.4-verification.md) are historical records.

## Remaining limits

- Static TrueType fonts have the broadest verification. Static CFF outlines are
  supported through fontTools; variable fonts, collections, webfonts and color-only
  glyphs are unsupported. Signs require a Unicode cmap entry and nonempty outline.
- Full vertical text flow, advanced baseline alignment and HieroTeX compatibility
  remain deferred. Deep nesting can make signs small; individual large quadrats
  cannot be split across lines.
- Hieropy's grammar determines accepted structure. Malformed joiners, unknown
  controls and invalid enclosure combinations produce explicit errors.
  Its dependency packages remain installed even though its layout is not used.
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
