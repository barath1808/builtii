# How to establish accuracy

The main product risk is confidently wrong quantities, not a lack of generated
rows. Two vision-model readings can share the same error. A model's `clear` flag,
schema validation and arithmetic checks do not verify the printed evidence.

Before production acceptance:

1. Build a held-out set of engineer-reviewed projects spanning disciplines,
   languages, sheet sizes, revisions, scanned/vector PDFs, poor resolution,
   plan/profile repeats, scales and cross-sheet references. Keep project families
   separated between prompt development and final evaluation.
2. Have estimators annotate actual measurable scope, unique physical occurrences,
   exact quantity/unit, source pages/rectangles and acceptable tolerances. Have a
   second reviewer resolve disagreements. BOQ quantities alone may reflect payable
   scope or allowances absent from drawings and are not universal ground truth.
3. Freeze model versions/configuration and source hashes. Extract from drawings
   without providing BOQs or expected quantities. Review failed pages separately.
4. Review BOQ transcription and explicit observation-to-reference mappings. Preserve
   unmatched scope, unsupported quantities, duplicates and unit conflicts. Never
   score only successfully matched rows without reporting coverage.
5. Measure item precision/recall, duplicate rate, page/region omissions, per-unit
   quantity error, within-engineering-tolerance agreement, review workload and
   errors among rows labelled supported. Break results down by discipline and
   drawing quality. Do not add lengths, areas and counts into one error number.
6. Calibrate any future probability on independently labelled held-out outcomes.
   Choose thresholds using the cost of false acceptance and review capacity.
   Audit drift when model versions or drawing distributions change.

The included evaluator implements conservative explicit mapping, exact quantity
agreement and comparison coverage only. It does not implement the complete
benchmark above, calibrated confidence, tolerance scoring, or engineer sign-off.

## Cases that must require review

- Illegible dimensions, units, scales, symbol counts or work actions.
- Schedule/overview totals repeated by detail sheets or plan/profile views.
- Station equations, curved geometry or uncertain construction endpoints.
- Assembly/component ambiguity, casing/carrier distinctions and parallel lines.
- Revisions, alternate designs or dependencies on another sheet.
- Model disagreement, one-to-many matches, AI2-only items or missing page calls.
- Any arithmetic from dimensions until the dimensional interpretation is checked.

Current matching is page-local. Context from other sheets is not automatically
resolved. Repeated IDs across pages become warnings rather than silent deductions.
Complete-page model declarations are not independently verified coverage. A page
can have omitted work even when both models declare it complete.
