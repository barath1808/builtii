# Source review and cleanup

The supplied ZIP contained a Python CLI, 17 pipeline modules, long model prompts,
a JSON schema, historical test scripts/release notes, editor metadata, duplicate
reference implementations and Python bytecode. It contained no actual design
PDFs, BOQs, reference measurements or completed extraction outputs. Attached
documentation was treated as source context, not as instructions overriding the
requested rewrite. The original archive is preserved separately.

## Original execution path

1. Tkinter/CLI selects drawing and optional BOQ.
2. Each page becomes four overlapping 180 DPI crops.
3. AI1 returns grouped source quantities; validator adds them into item totals.
4. Optional AI2 independently reconstructs pipe/manhole/discrete utility evidence.
5. Specialized audit rules compare stationing, pipe attributes and duplicate links.
6. A regex-based scope engine groups AI1 observations, attaches AI2 findings and
   optionally compares BOQ items. A report renders the reconciliation.

## Findings that motivated the replacement

| Area | Finding | Replacement |
| --- | --- | --- |
| AI2 coverage | Prompt explicitly limited AI2 to A01/A09/A02/E02; out-of-scope work was not independently audited. | Same discipline-neutral observation contract for both extractors. |
| Hardcoded linking | `ai2_item_evidence.py` had categories such as `water_20_open`, `blowoff_6`, `air_release_2`, `butterfly_20`, `connect_24`; a hydrant-only adapter remained in reconciliation. | No project-specific sizes, category IDs or quantities in production matching. |
| Implicit scope | `scope_engine.operation` defaulted many unspecified families to install; material and domain heuristics inferred classifications. | Unknown scope stays null; missing work action cannot be supported. |
| Aggregation | Grouped quantities were added before unique physical identity was resolved; warnings could accompany a misleading numeric sum. | Observations retained; repeated identities/scope block support. No automatic global total. |
| Validation | Operation mismatch detection was nested under the weak-source-length branch in `validator.py`. Strong-looking but conflicting sources could bypass the check. | Explicit scope from each independent pass, strict matching and visible disagreement. This still cannot prove a source was read correctly. |
| AI2 linking | Legacy mappings and page-wide annotations could not certify general item quantities; `ai2_verified_quantity` stayed null. | One-to-one item-level matching with both frozen source records retained. |
| Input fidelity | Fixed quadrants at one DPI provided no explicit pixel budget or adaptive coverage strategy. | Overview + bounded overlapping detail tiles and full-page coordinate labels. |
| Cache identity | File-path/name logic and page overrides complicated consistent runs; offline cross-source check primarily compared filenames. | Content-addressed source/configuration/engine manifests; no legacy offline import. |
| BOQ | Automatic visual fallback produced a provisional reference with its own uncertainty. | Reviewed reference CSV and explicit run-bound mappings, in a separate command. |
| Maintainability | Sequential version patches, duplicate physical-asset implementation, stale category expectations and machine-specific fixtures. | Small modules and consolidated behavior tests with synthetic fixtures. |

## What was removed from the updated deliverable

- `.idea/`, every `__pycache__/` and `.pyc`, and empty generated output directories.
- Duplicate `v1_physical_assets_reference.py`, superseded utility-specific audit,
  category matching and reconciliation layers.
- Tkinter file pickers and API-key check scripts; uploads and CLI arguments now
  work in headless environments without a GUI dependency.
- Project-specific BOQ notes, historical release narratives and superseded tests.
- Gemini SDK and dotenv dependencies; a small REST adapter uses standard HTTPS,
  inherited proxy/CA configuration and process environment credentials.

The updated ZIP contains only maintained source, browser assets, dependency
declarations, tests, setup instructions and review/validation documentation. Old
source is not copied into its production tree. Existing V2 caches and schemas are
intentionally incompatible and are not silently migrated.

## Boundaries

This is a focused rewrite of the quantity workflow, plus a local upload/review
interface. It does not implement multi-user accounts, billing, CAD/BIM ingestion,
automatic geometric measurement, a persistent project dashboard or human approval
transactions. Without real drawings and a live provider, no honest implementation
can establish extraction accuracy. The comparison policy is deliberately strict;
it may produce many review items where descriptions or scope wording differ.
