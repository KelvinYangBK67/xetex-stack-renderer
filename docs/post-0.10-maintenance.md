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
