"""Synthetic engineering fixtures only; never production fallback quantities."""
from copy import deepcopy
import pymupdf


def item(quantity=12, description="Install structural member", asset="B1", action="install", box=None):
    return {"description": description, "scope": {"work_type": "structural member", "action": action,
            "material": "steel", "specification": "size per printed label", "method": None},
            "unit": "EA", "asset_id": asset, "identity_context": "Building A / grid 1",
            "representation": "installation", "measurement": {"operation": "printed",
            "operands": [{"value": quantity, "unit": "EA", "quote": f"{quantity} members"}],
            "explanation": "Explicit printed count"}, "evidence": [{"quote": f"{quantity} members",
            "location": "grid 1 at member B1", "bbox": box or [.1,.2,.4,.5]}],
            "quality": "clear", "uncertainties": []}


def page(items=None, number=1):
    return {"page": number, "sheet_title": "SYNTHETIC TEST SHEET", "items": [item()] if items is None else items,
            "review_regions": [], "coverage": "complete"}


def make_pdf(path, pages=1):
    with pymupdf.open() as doc:
        for _ in range(pages):
            p = doc.new_page(width=612, height=792)
            p.insert_text((60,100), "SYNTHETIC TEST - 12 steel members at grid 1")
        doc.save(path)


class FakeProvider:
    models = {"ai1": "test-extractor", "ai2": "test-auditor"}

    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail

    def extract(self, stage, images, number, total):
        self.calls.append((stage, number))
        if stage == self.fail:
            raise RuntimeError("Synthetic test failure")
        result = page(number=number)
        result["items"][0]["asset_id"] = f"B{number}"
        return deepcopy(result)
