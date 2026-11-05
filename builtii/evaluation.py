"""Separate, explicit held-out BOQ evaluation; never feeds extraction."""
import csv
import json
from decimal import Decimal
from pathlib import Path
from .schema import decimal, unit
from .pipeline import sha_file


def evaluate(report_path, reference_path, mapping_path):
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    mapping_doc = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    if mapping_doc.get("run_id") != report["run_id"]:
        raise ValueError("Mapping belongs to a different extraction run")
    mappings = mapping_doc.get("items", {})
    observations = {r["id"]: r for r in report["rows"]}
    references, seen = [], set()
    with Path(reference_path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not {"item_no", "description", "quantity", "unit"} <= set(reader.fieldnames or []):
            raise ValueError("Reference CSV needs item_no,description,quantity,unit")
        for row in reader:
            if not row["item_no"].strip() or row["item_no"] in seen or not row["description"].strip() or not row["unit"].strip():
                raise ValueError("Invalid or duplicate reference row")
            seen.add(row["item_no"])
            row["quantity"] = str(decimal(row["quantity"]))
            references.append(row)
    if not references or not isinstance(mappings, dict) or set(mappings) - seen:
        raise ValueError("Empty reference or unknown mapping item numbers")
    assigned, rows = set(), []
    for ref in references:
        ids = mappings.get(ref["item_no"], [])
        if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids):
            raise ValueError("Mapping must contain unique observation ID lists")
        if assigned.intersection(ids) or any(i not in observations for i in ids):
            raise ValueError("Unknown or multiply allocated observation")
        assigned.update(ids)
        selected = [observations[i] for i in ids]
        status, q = "unmapped", None
        if selected:
            if any(unit(r["unit"]) != unit(ref["unit"]) for r in selected):
                raise ValueError("Mapped units conflict; no automatic conversions")
            if any(r["status"] != "supported" or r["quantity"] is None for r in selected) or not report["processing_complete"]:
                status = "blocked_by_review"
            else:
                q = sum((Decimal(r["quantity"]) for r in selected), Decimal(0))
                status = "equal" if q == Decimal(ref["quantity"]) else "different"
        delta = q - Decimal(ref["quantity"]) if q is not None else None
        rows.append({**ref, "observation_ids": ids, "extracted_quantity": str(q) if q is not None else None,
                     "difference": str(delta) if delta is not None else None, "status": status})
    comparable = sum(r["status"] in ("equal", "different") for r in rows)
    equal = sum(r["status"] == "equal" for r in rows)
    return {"run_id": report["run_id"], "reference_sha256": sha_file(reference_path), "mapping_sha256": sha_file(mapping_path),
            "rows": rows, "unallocated_observations": sorted(set(observations)-assigned),
            "metrics": {"reference_items": len(rows), "comparable_items": comparable, "equal_items": equal,
                        "comparison_coverage": comparable/len(rows), "exact_agreement": equal/comparable if comparable else None},
            "accuracy_percentage": None,
            "notice": "Held-out reference agreement with explicit human mappings. Reference transcription and mapping must be reviewed. Not engineering accuracy or proof of missing-item recall."}
