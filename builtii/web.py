"""Single-user local workbench. Bind to loopback; no public deployment assumptions."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import shutil
import threading
import uuid
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .pdf import inspect, MAX_BYTES
from .pipeline import run, save_json
from .provider import Gemini


def create_app(data_dir=None, provider_factory=Gemini):
    root = Path(data_dir or os.environ.get("BUILTII_DATA_DIR", "data")).resolve()
    root.mkdir(parents=True, exist_ok=True)
    jobs, guard = {}, threading.Lock()
    pool = ThreadPoolExecutor(max_workers=1)
    static = Path(__file__).parent / "static"

    @asynccontextmanager
    async def lifespan(app):
        yield
        pool.shutdown(wait=True)

    app = FastAPI(title="Builtii drawing review", lifespan=lifespan)

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        # Browser cross-site uploads must not spend the local user's API quota.
        from urllib.parse import urlsplit
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin:
            if urlsplit(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "Cross-origin request rejected"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def update(job, **changes):
        with guard:
            jobs[job].update(changes)
            save_json(root / job / "status.json", jobs[job])

    def process(job, provider):
        update(job, state="running")
        try:
            folder, report = run(root/job/"drawing.pdf", root/job/"runs", provider,
                                 progress=lambda done, total, message: update(job, done=done, total=total, message=message))
            update(job, state="completed" if report["processing_complete"] else "incomplete", run=folder.name,
                   summary=report["summary"], message="Review quantities and source regions")
        except Exception:
            update(job, state="failed", message="Could not process PDF; check input and server configuration")

    @app.get("/")
    def index():
        return FileResponse(static / "index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "provider_configured": bool(os.environ.get("GEMINI_API_KEY")),
                "mode": "local-single-user", "accuracy": "unmeasured"}

    @app.post("/api/jobs", status_code=202)
    async def upload(file: UploadFile = File(...)):
        with guard:
            if any(j["state"] in ("uploading", "queued", "running") for j in jobs.values()):
                raise HTTPException(409, "A drawing is already being processed")
            job = uuid.uuid4().hex
            jobs[job] = {"id": job, "state": "uploading", "done": 0, "total": 0}
        directory = root/job
        directory.mkdir()
        try:
            size = 0
            with (directory/"drawing.pdf").open("wb") as stream:
                while chunk := await file.read(1024*1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ValueError("PDF exceeds 100 MiB limit")
                    stream.write(chunk)
            total = inspect(directory/"drawing.pdf")
            try:
                provider = provider_factory()
            except Exception:
                raise HTTPException(503, "Gemini is not configured; set GEMINI_API_KEY on the server") from None
            update(job, state="queued", total=total, message="Waiting for extraction")
            pool.submit(process, job, provider)
            return {"id": job}
        except (ValueError, RuntimeError) as exc:
            with guard:
                jobs.pop(job, None)
            shutil.rmtree(directory)
            raise HTTPException(400, str(exc)) from None
        except BaseException:
            with guard:
                jobs.pop(job, None)
            shutil.rmtree(directory)
            raise
        finally:
            await file.close()

    def status(job):
        if not __import__("re").fullmatch(r"[a-f0-9]{32}", job):
            raise HTTPException(404, "Job not found")
        with guard:
            if job in jobs:
                return dict(jobs[job])
        try:
            saved = json.loads((root/job/"status.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise HTTPException(404, "Job not found") from None
        if saved["state"] in ("queued", "running", "uploading"):
            saved.update(state="interrupted", message="Server restarted; resume with the CLI to reuse cached pages")
        return saved

    @app.get("/api/jobs/{job}")
    def job_status(job: str):
        return status(job)

    @app.get("/jobs/{job}/{asset:path}")
    def artifact(job: str, asset: str):
        current = status(job)
        run_id = current.get("run")
        if not run_id:
            raise HTTPException(404, "Report not available yet")
        import re
        if asset not in ("report.html", "report.json", "quantities.csv") and not re.fullmatch(r"previews/[1-9][0-9]*\.png", asset):
            raise HTTPException(404, "Artifact not found")
        path = root/job/"runs"/run_id/asset
        if not path.is_file():
            raise HTTPException(404, "Artifact not found")
        return FileResponse(path)

    app.mount("/static", StaticFiles(directory=static), name="static")
    return app
