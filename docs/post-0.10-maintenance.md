# Post-0.10 maintenance: issues #1 and #2

Public release version remains 0.10. The starting commit is
`c2dfb1e29fc985e449a0efbb19f9b65dac1a5fd3` (993 tests passed locally).

## Issue #1: preprocess artifacts

- Ordinary preprocess writes `.xsr/<job>.responses.tex` and
  `.xsr/<job>.manifest.json` beneath the output directory. There are no individual
  response files, request files or default persistent cache.
- All logical runs keep the existing request digest, including backend version,
  options and source identity. The manifest identifies one shared bundle plus
  each digest key. Responses are deduplicated, ordered by digest and written
  atomically; a successful rerun replaces the complete set of entries.
- TeX stores unexpanded response bodies and evaluates them at use time. Font
  metrics, scale and raise are not frozen. Bundle declarations emit no spacing.
- Missing bundle/digest diagnostics are `XSR-BUNDLE-MISSING` and
  `XSR-RESPONSE-MISSING`; malformed bodies retain `XSR-RESPONSE` validation.
- Default renderer/provider acquisition is cacheless. Provider results live in
  temporary directories that are removed after acquisition, with in-memory reuse
  across requests in one renderer. Structured argv, shell=False, timeout, output
  size limits, restricted SVG validation and typed failures remain intact.
- `--cache-dir` is an explicit persistent-cache opt-in. The TeX `cache-dir` option
  serves the same purpose in shell mode. Persistent SVG is still revalidated.
- Shell mode uses one fixed scratch pair, consumes requests, stores responses
  in memory and cleans the pair after the last page. Failed/interrupted builds
  may retain a scratch response. Auto mode prefers a matching bundle entry.
- Existing legacy artifacts are ignored, not deleted automatically; shared old
  cache directories are not assumed to belong exclusively to the current job.

Seventeen new tests cover 19-asset documents, deterministic overwrite, changed
and removed inputs, provider deduplication/cleanup, explicit cache opt-in,
validation failures, atomic failure, typed missing entries, no-shell and auto
compilation, separate output directories, shell cleanup and runtime geometry.
The showcase builders and prior manifest/response assertions use the new bundle.

## Issue #2: optical image alignment

`GlyphPolicy.vertical_bias_fraction` is explicitly zero for vectors and -0.12
for images, including manual PDF assets. For cell size C, current cell center,
use-site scale s and normalized canvas height h, the final image shift is:

```text
shift = center - h/2 - 0.12*(C*s) + user_raise
```

The serialized response carries both alignment and bias in its policy argument;
TeX computes the bias with the same scaled ideographic unit as Python. User
raise remains additive, including when compensating the bias. Image alpha 1.10,
vector alpha 1.00, image side bearing -0.02, aspect ratio and honest box metrics
are unchanged. No image processing or PDF-content inspection is introduced.

`INLINE_VERSION` and the vector/provider/asset TeX registrations now use
`inline-0.10-optical-1`. This changes request and persistent response identities,
so older geometry or response formats cannot be reused silently. Public package
version remains 0.10; the restricted SVG importer and font backends are unchanged.

Additional tests cover policy defaults, scaled bias and additive compensation,
unchanged vector geometry, metadata-only PNG/JPEG/PDF handling, measured TeX
metrics across sizes for each image format, and rejection of an old-policy
bundle. The ideographic-font and tall-line-spacing tests remain in the suite.

The -0.12 default comes from the reported real Chinese article experiment.
Verification here uses the repository's original neutral fixtures and synthetic
ideographic font; it does not claim a second independent palaeographic corpus
has established a universally optimal correction. Per-source raise remains
available for that reason.

## Verification

Focused geometry/TeX/bundle/provider/include/renderer/preprocess selection:
**173 passed, 0 skipped, 2 expected aspect-ratio warnings**.

All four showcases rebuilt without shell escape. Egyptian (6 pages), Khitan
(5 pages) and vector/provider (3 pages) have pixel-identical renders to the 0.10
baseline at 108 dpi, confirming unchanged font/vector alignment and transport
spacing. The updated four-page inline showcase was rendered with Poppler and
visually inspected. Regression PDFs remain untracked test outputs; only the
intentionally updated inline showcase PDF/source is committed.

Final full-suite and separate-integration results are reported at completion.
The CI integration selection includes the new bundle tests. No public package
version bump or dependency change was needed.
