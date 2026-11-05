"""Bounded rendering: overview plus overlapping full-resolution detail tiles."""
from dataclasses import dataclass
import math
from pathlib import Path
import pymupdf

MAX_BYTES = 100 * 1024 * 1024
MAX_PAGES = 200
RENDER_VERSION = "overview-1200-detail-220dpi-1600px-overlap80-v1"


@dataclass
class Image:
    label: str
    data: bytes


def inspect(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("PDF exceeds 100 MiB limit")
    try:
        with pymupdf.open(path) as doc:
            if not doc.is_pdf or doc.needs_pass or not 1 <= len(doc) <= MAX_PAGES:
                raise ValueError("An unencrypted PDF with 1–200 pages is required")
            return len(doc)
    except pymupdf.FileDataError as exc:
        raise ValueError("Invalid or damaged PDF") from exc


def render(path, number, previews):
    previews = Path(previews)
    previews.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(path) as doc:
        page = doc[number - 1]
        rect = page.rect
        if rect.width <= 0 or rect.height <= 0:
            raise ValueError("Invalid page dimensions")
        scale = min(1200 / max(rect.width, rect.height), 2)
        overview = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False,
                                   colorspace=pymupdf.csRGB).tobytes("png")
        (previews / f"{number}.png").write_bytes(overview)
        images = [Image("Full page overview [0,0,1,1]", overview)]
        tile = 1600 * 72 / 220
        stride = 1520 * 72 / 220
        nx = max(1, math.ceil(max(0, rect.width - tile) / stride) + 1)
        ny = max(1, math.ceil(max(0, rect.height - tile) / stride) + 1)
        if nx * ny > 64:
            raise ValueError("Sheet requires over 64 detail tiles; split the oversized sheet before extraction")
        for y in range(ny):
            for x in range(nx):
                x0, y0 = min(x * stride, max(0, rect.width - tile)), min(y * stride, max(0, rect.height - tile))
                clip = pymupdf.Rect(x0, y0, min(x0 + tile, rect.width), min(y0 + tile, rect.height))
                box = [round(clip.x0 / rect.width, 6), round(clip.y0 / rect.height, 6),
                       round(clip.x1 / rect.width, 6), round(clip.y1 / rect.height, 6)]
                pix = page.get_pixmap(dpi=220, clip=clip, alpha=False, colorspace=pymupdf.csRGB)
                images.append(Image(f"Detail tile {x+1},{y+1}; full-page bounds={box}", pix.tobytes("png")))
        return images
