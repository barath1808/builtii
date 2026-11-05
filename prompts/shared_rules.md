Inspect the full sheet and ALL detail tiles as ONE sheet. Coordinates on
tiles are normalized to the FULL PAGE (top-left origin); all returned bboxes use
that coordinate system. Overlapping tiles, plan/profile, schedules and overview
views can repeat ONE asset. Retain distinct observations with identity clues;
do not add their quantities. One item represents one physical occurrence or one
explicitly printed aggregate, never an inferred group of unrelated assets.

Search every discipline shown: civil, architectural, structural, mechanical,
electrical, landscape, restoration and demolition. Do not restrict audit scope.
Preserve work action, component vs assembly, size, material, grade, method and unit.
Unknown fields are null, NEVER default installation, material, method or size.
Asset IDs and identity_context must be visible drawing labels; context identifies
the alignment/building/grid, not a model-invented ID. No unique ID: use null.

Every item needs a faithful source quote or truthful description of visible symbols,
a specific location and bbox if reliably locatable (otherwise null). For dimensions,
each operand includes its own verbatim source quote and unit. Python computes
sum/product/difference. Printed quantities/counts use one operand. Count only
distinct located symbols, explain the count. For unsupported quantities use
operation=unresolved and keep an item with uncertainty; NEVER guess or silently
omit it. Do not measure pixels, assume scale, use viewport station limits as
installation limits, infer typical widths/depths or convert incompatible units.
Station subtraction is only a candidate when actual construction endpoints and
continuous stationing are explicit; explain curves, equations and exclusions.

Existing-to-remain, legends, generic details and notes alone do not establish
installed work. If retained for review, use representation=typical_detail/unknown
and unresolved quantity. Summaries and schedules are not extra installations.
Distinguish casing/carrier, new/removal/replacement and separate parallel assets.

Report every unreadable, ambiguous, dependent-on-other-sheet or not-inspected
region with reason and full-page bbox if possible. coverage=complete only if the
whole sheet is legible and inspected, NOT just because some items were found.
An empty page with uncertainty must be partial/unreadable and have review_regions.
Model quality is a reading assessment, NOT an accuracy probability.
