"""Content-addressed, resumable extraction with explicit page failures."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import tempfile
from . import __version__
from . import audit, pdf, prompts, schema
from .report import write_report


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            json.dump(data, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    temp.replace(path)


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(path, output, provider, progress=None, force=False):
    path, output = Path(path), Path(output)
    total = pdf.inspect(path)
    # Hash actual engine code, prompts and schema; old configurations never share caches.
    engine = hashlib.sha256()
    for source in sorted(Path(__file__).parent.glob("*.py")):
        engine.update(source.name.encode())
        engine.update(source.read_bytes())
    manifest = {"source_sha256": sha_file(path), "models": provider.models,
                "prompts_sha256": prompts.fingerprint(),
                "engine_sha256": engine.hexdigest(), "render": pdf.RENDER_VERSION,
                "version": __version__, "pages": total}
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    folder = output / fingerprint
    folder.mkdir(parents=True, exist_ok=True)
    save_json(folder / "manifest.json", manifest)
    results, errors = {"ai1": [], "ai2": []}, []
    for page in range(1, total+1):
        if progress:
            progress(page-1, total, f"Inspecting page {page} of {total}")
        pending = []
        for stage in ("ai1", "ai2"):
            cache = folder / "cache" / f"{stage}-{page}.json"
            if cache.exists() and not force:
                try:
                    data = json.loads(cache.read_text(encoding="utf-8"))
                    results[stage].append(schema.validate_page(data, page))
                    continue
                except (ValueError, OSError, TypeError):
                    pass
            pending.append((stage, cache))
        try:
            images = pdf.render(path, page, folder / "previews")
        except Exception:
            errors.append({"page": page, "stage": "render", "message": "Page rendering failed; inspect source PDF size and geometry"})
            if force:
                for _, cache in pending:
                    cache.unlink(missing_ok=True)
            continue
        # Only the two independent calls for this page are in memory at once.
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [(stage, cache, pool.submit(provider.extract, stage, images, page, total)) for stage, cache in pending]
            for stage, cache, future in futures:
                try:
                    data = schema.validate_page(future.result(), page)
                    save_json(cache, schema.raw_page(data))
                    results[stage].append(data)
                except Exception as exc:
                    from .provider import ProviderError
                    message = str(exc) if isinstance(exc, ProviderError) else "Extraction or schema validation failed; page requires review"
                    errors.append({"page": page, "stage": stage, "message": message})
                    # A forced refresh must never resurrect an older successful response.
                    cache.unlink(missing_ok=True)
        if progress:
            progress(page, total, f"Completed page {page} of {total}")
    report = audit.reconcile(results["ai1"], results["ai2"], total, errors)
    report.update({"source_sha256": manifest["source_sha256"], "run_id": fingerprint,
                   "models": provider.models, "engine_sha256": manifest["engine_sha256"]})
    save_json(folder / "report.json", report)
    write_report(folder, report)
    return folder, report
