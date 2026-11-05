# Validation evidence

Validated on Python 3.12 in the supplied cloud workspace.

| Check | Result and scope |
| --- | --- |
| `python -m unittest discover -v` | 45 tests passed; no skipped tests. Synthetic fixtures and injected provider responses. |
| Core drawing pipeline | Real PyMuPDF rendering, two frozen test-provider passes, strict validation, reconciliation and HTML/CSV/JSON outputs exercised end to end. |
| Failure handling | Missing/failed auditor, malformed schema, nonfinite values, corrupt caches, forced-refresh failures and rendering failures exercised. |
| Evidence matching | Conflicting quantities, operations, distinct identities, repeated plan/profile observations, unknown identity and many-to-many matches exercised. |
| Arithmetic | Decimal sums, dimensional products, incompatible units and unsupported quantities exercised. |
| Evaluation isolation | Reviewed-reference mapping, run identity, double-allocation rejection, comparison coverage and unchanged drawing artifacts verified. |
| HTTP API | Upload, job completion, report/CSV/source image access, invalid-PDF cleanup, missing credentials, cross-origin rejection and artifact restrictions exercised. |
| Browser workflow | System Chromium: desktop/mobile layout, synthetic PDF upload, completed report, source image expansion, search and status filtering passed. No browser JavaScript errors. |
| Actual server | `python main.py serve` started; local HTTP health request returned `status=ok` and `provider_configured=false`. |
| Distribution | Wheel built and installed locally with `--no-index --no-deps --no-build-isolation`; application code and static assets packaged. |
| Static checks | Python compilation and `node --check web/static/app.js` passed. |

The cloud command sandbox initially prevented loopback binding and caused the
synchronous test client's event loop to hang. The server, interface suite and
browser checks succeeded with authorized local networking enabled. This was a
test-environment restriction, not an application failure. The installed Starlette
test client emits a deprecation warning about its httpx transport; tests pass.

Prompt-file composition, prompt cache-fingerprint changes and invalid-stage rejection
are also covered. Schema-file changes invalidate run caches. The reorganized wheel
was installed and imported outside the checkout, confirming main/config modules,
pipeline modules, all four prompt files, the JSON schema and browser assets are
packaged. No retired nested application package is shipped.

## Not verified

- Live Gemini requests: no `GEMINI_API_KEY` is configured.
- Real engineering drawing accuracy: no drawings or labelled takeoff ground truth
  were included in the uploaded ZIP.
- BOQ benchmark accuracy: no real reviewed BOQ/mapping set was supplied.
- Fresh Internet dependency download: tests used the packages already installed
  in the environment. Wheel packaging was verified without network downloads.
- Production concurrency, tenant separation, malicious-PDF isolation, durable job
  recovery, engineer approval history and load testing are outside this local MVP.

Synthetic fixture quantities exist only in tests. The production engine has no
fixture fallback, expected project totals or PDF-name-specific branches. Passing
these tests demonstrates software behavior, not model extraction accuracy.
