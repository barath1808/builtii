"""Reconcile frozen observations without a BOQ, fuzzy quantity matching or guessing."""
from collections import Counter, defaultdict
from decimal import Decimal
from pipeline.validator import normalized, unit


def scope(item):
    return tuple(normalized(item["scope"][k]) for k in ("work_type", "action", "material", "specification", "method")) + (unit(item["unit"]),)


def overlap(a, b):
    if a is None or b is None:
        return 0
    area = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - area
    return area / union if union else 0


def identity(item):
    if item["asset_id"] and item["identity_context"]:
        return normalized(item["identity_context"]), normalized(item["asset_id"])
    return None


def candidate(a, b):
    # Quantities are deliberately excluded from matching.
    if scope(a) != scope(b):
        return False
    if identity(a) and identity(b):
        return identity(a) == identity(b)
    return any(overlap(x["bbox"], y["bbox"]) >= .5 and normalized(x["location"]) == normalized(y["location"])
               for x in a["evidence"] for y in b["evidence"])


def reconcile(ai1, ai2, total, errors):
    rows, regions, page_status = [], [], []
    left, right = {p["page"]: p for p in ai1}, {p["page"]: p for p in ai2}
    for page in range(1, total + 1):
        a, b = left.get(page), right.get(page)
        complete = a is not None and b is not None
        page_status.append({"page": page, "ai1": a["coverage"] if a else "failed",
                            "ai2": b["coverage"] if b else "failed"})
        for stage, data in (("ai1", a), ("ai2", b)):
            if data:
                regions.extend({"page": page, "stage": stage, **r} for r in data["review_regions"])
                if data["coverage"] != "complete" and not data["review_regions"]:
                    regions.append({"page": page, "stage": stage, "bbox": None, "reason": "Incomplete drawing inspection"})
            else:
                regions.append({"page": page, "stage": stage, "bbox": None, "reason": "Extraction unavailable; review whole page"})
        aa, bb = a["items"] if a else [], b["items"] if b else []
        matches = [[j for j, other in enumerate(bb) if candidate(item, other)] for item in aa]
        reverse = Counter(j for js in matches for j in js)
        used = set()
        for i, item in enumerate(aa):
            js = matches[i]
            j = js[0] if len(js) == 1 and reverse[js[0]] == 1 else None
            other = bb[j] if j is not None else None
            if j is not None:
                used.add(j)
            reasons = list(item["uncertainties"])
            if any(error["page"] == page for error in errors):
                reasons.append("Page processing or rendering failed")
            if not complete:
                reasons.append("Independent page extraction missing")
            if j is None:
                reasons.append("No unique independent evidence match" if not js else "Ambiguous many-to-many evidence matches")
            observations = [item] + ([other] if other else [])
            for obs in observations:
                reasons.extend(obs["uncertainties"])
                if obs["quality"] != "clear":
                    reasons.append("Source reading is ambiguous or unreadable")
                if obs["computed_quantity"] is None:
                    reasons.append("Quantity cannot be computed from supported evidence")
                if obs["representation"] != "installation":
                    reasons.append("Schedule/overview/detail or unknown representation needs physical scope review")
                if not obs["scope"]["action"] or not obs["scope"]["work_type"]:
                    reasons.append("Work type or action unspecified")
                if obs["scope"]["action"] == "remain":
                    reasons.append("Existing-to-remain is not a new measurable work instruction")
                if not any(e["bbox"] for e in obs["evidence"]):
                    reasons.append("Source region not located")
                if obs["measurement"]["operation"] not in ("printed", "count"):
                    reasons.append("Calculated dimensions/count assumptions require engineering review")
            if complete and (a["coverage"] != "complete" or b["coverage"] != "complete" or a["review_regions"] or b["review_regions"]):
                reasons.append("Page contains unresolved coverage or regions")
            if other and item["computed_quantity"] is not None and other["computed_quantity"] is not None:
                if Decimal(item["computed_quantity"]) != Decimal(other["computed_quantity"]):
                    reasons.append("Independent quantities disagree")
            rows.append({"id": f"p{page}-ai1-{i+1}", "page": page, "description": item["description"],
                         "unit": unit(item["unit"]), "quantity": item["computed_quantity"],
                         "ai2_quantity": other["computed_quantity"] if other else None,
                         "ai1": item, "ai2": other, "reasons": sorted(set(reasons)),
                         "status": "review_required" if reasons else "supported"})
        for j, item in enumerate(bb):
            if j not in used:
                rows.append({"id": f"p{page}-ai2-{j+1}", "page": page, "description": item["description"],
                             "unit": unit(item["unit"]), "quantity": None, "ai2_quantity": item["computed_quantity"],
                             "ai1": None, "ai2": item, "status": "review_required",
                             "reasons": ["AI2-only or ambiguously matched observation; possible AI1 omission"]})
    # Bucket repetitions rather than performing a quadratic project-wide scan.
    identities, scopes = defaultdict(list), defaultdict(list)
    for row in rows:
        item = row["ai1"] or row["ai2"]
        if identity(item):
            identities[(identity(item), normalized(item["scope"]["work_type"]))].append(row)
        scopes[scope(item)].append(row)

    def mark_repeat(group):
        ids = [r["id"] for r in group]
        for row in group:
            peers = [i for i in ids[:11] if i != row["id"]][:10]
            row["reasons"].append(f"Possible repeated asset/scope ({len(group)} observations; related: {', '.join(peers)}); resolve physical identity before totaling")
            row["status"] = "review_required"

    for group in identities.values():
        if len(group) > 1:
            mark_repeat(group)
    for group in scopes.values():
        if len(group) > 1 and any(not identity(r["ai1"] or r["ai2"]) for r in group):
            mark_repeat(group)
    counts = Counter(r["status"] for r in rows)
    return {"schema_version": "6.0", "rows": rows, "review_regions": regions, "pages": page_status,
            "errors": errors, "processing_complete": len(left) == len(right) == total and not errors,
            "accuracy_percentage": None,
            "summary": {"observations": len(rows), "supported": counts["supported"], "review_required": counts["review_required"],
                        "pages": total, "ai1_pages": len(left), "ai2_pages": len(right)},
            "notice": "Supported means clear, uniquely matched AI evidence with equal quantities. It is not calibrated accuracy, completeness, or engineer approval. No automatic project totals are produced."}
