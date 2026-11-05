"""One strict, discipline-neutral contract for both independent extractors."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import json
from jsonschema import Draft202012Validator


def obj(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


TEXT = {"type": "string", "minLength": 1, "maxLength": 4000}
NULL_TEXT = {"anyOf": [TEXT, {"type": "null"}]}
BBOX = {"anyOf": [{"type": "array", "items": {"type": "number", "minimum": 0, "maximum": 1},
                       "minItems": 4, "maxItems": 4}, {"type": "null"}]}
EVIDENCE = obj({"quote": TEXT, "location": TEXT, "bbox": BBOX})
OPERAND = obj({"value": {"type": "number", "minimum": 0}, "unit": TEXT, "quote": TEXT})
MEASUREMENT = obj({"operation": {"enum": ["printed", "count", "sum", "product", "difference", "unresolved"]},
                   "operands": {"type": "array", "items": OPERAND, "maxItems": 200},
                   "explanation": TEXT})
SCOPE = obj({k: NULL_TEXT for k in ("work_type", "action", "material", "specification", "method")})
SCOPE["properties"]["action"] = {"enum": [None, "install", "remove", "replace", "relocate", "rehabilitate",
                                                   "protect", "modify", "reconnect", "connect", "abandon", "remain"]}
ITEM = obj({"description": TEXT, "scope": SCOPE, "unit": TEXT,
            "asset_id": NULL_TEXT, "identity_context": NULL_TEXT,
            "representation": {"enum": ["installation", "schedule", "overview", "typical_detail", "unknown"]},
            "measurement": MEASUREMENT,
            "evidence": {"type": "array", "items": EVIDENCE, "minItems": 1, "maxItems": 200},
            "quality": {"enum": ["clear", "ambiguous", "unreadable"]},
            "uncertainties": {"type": "array", "items": TEXT}})
PAGE_SCHEMA = obj({"page": {"type": "integer", "minimum": 1}, "sheet_title": NULL_TEXT,
                   "items": {"type": "array", "items": ITEM, "maxItems": 1000},
                   "review_regions": {"type": "array", "items": obj({"reason": TEXT, "bbox": BBOX})},
                   "coverage": {"enum": ["complete", "partial", "unreadable"]}})


def normalized(value):
    return " ".join((value or "").casefold().split())


def unit(value):
    key = normalized(value)
    return {"each": "EA", "ea": "EA", "no": "EA", "lf": "FT", "ft": "FT", "feet": "FT",
            "linear feet": "FT", "sf": "FT2", "sq ft": "FT2", "ft2": "FT2",
            "cf": "FT3", "ft3": "FT3", "sy": "YD2", "cy": "YD3", "yd": "YD",
            "m": "M", "m2": "M2", "m²": "M2", "m3": "M3", "m³": "M3",
            "mm": "MM", "ls": "LS", "lump sum": "LS", "1": "1"}.get(key, key.upper())


def decimal(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a quantity")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Invalid quantity") from exc
    if not result.is_finite() or result < 0 or result > Decimal("1e15"):
        raise ValueError("Quantity must be finite, nonnegative and <= 1e15")
    return result


def quantity(item):
    """Compute supported arithmetic, without eval, scale guesses or unit conversion."""
    m = item["measurement"]
    op, operands, target = m["operation"], m["operands"], unit(item["unit"])
    if op == "unresolved":
        return None
    values = [decimal(x["value"]) for x in operands]
    units = [unit(x["unit"]) for x in operands]
    if not values:
        raise ValueError("Measurement has no operands")
    if op in ("printed", "count"):
        if len(values) != 1 or units != [target]:
            raise ValueError("Printed/count measurement requires one matching-unit operand")
        if op == "count" and (target != "EA" or values[0] != values[0].to_integral_value()):
            raise ValueError("Counts must be integral EA")
        result = values[0]
    elif op in ("sum", "difference"):
        if any(u != target for u in units) or (op == "difference" and len(values) != 2):
            raise ValueError("Invalid arithmetic units or operand count")
        result = sum(values, Decimal(0)) if op == "sum" else values[0] - values[1]
    else:
        # Multiplication supports explicit dimensions in one length system and
        # dimensionless multipliers. Mixed systems require reviewed conversion.
        dimensions = {"FT": ("FT", 1), "FT2": ("FT", 2), "FT3": ("FT", 3),
                      "M": ("M", 1), "M2": ("M", 2), "M3": ("M", 3),
                      "YD": ("YD", 1), "YD2": ("YD", 2), "YD3": ("YD", 3)}
        physical = [u for u in units if u != "1"]
        if len(physical) == 1 and physical[0] == target:
            pass
        elif physical and all(u in dimensions for u in physical) and target in dimensions:
            base, exponent = dimensions[target]
            if any(dimensions[u][0] != base for u in physical) or sum(dimensions[u][1] for u in physical) != exponent:
                raise ValueError("Product dimensions do not match output unit")
        else:
            raise ValueError("Unsupported product units")
        result = Decimal(1)
        for value in values:
            result *= value
    result = decimal(result)
    if target == "EA" and result != result.to_integral_value():
        raise ValueError("EA quantity must be integral")
    return str(result)


def validate_page(data, page):
    errors = list(Draft202012Validator(PAGE_SCHEMA).iter_errors(data))
    if errors:
        # Do not put arbitrary remote response bodies in logs.
        raise ValueError("Model response violates the extraction schema at " + "/".join(map(str, errors[0].absolute_path)))
    if data["page"] != page:
        raise ValueError("Response page does not match input")
    result = deepcopy(data)
    for region in result["review_regions"] + [e for i in result["items"] for e in i["evidence"]]:
        b = region["bbox"]
        if b is not None and (b[0] >= b[2] or b[1] >= b[3]):
            raise ValueError("Invalid evidence rectangle")
    for item in result["items"]:
        # Literal placeholders are unknown, not physical identifiers or scope.
        for key, value in item["scope"].items():
            if normalized(value) in ("unknown", "unspecified", "n/a", "not known"):
                item["scope"][key] = None
        for key in ("asset_id", "identity_context"):
            if normalized(item[key]) in ("unknown", "unspecified", "n/a", "not known"):
                item[key] = None
        for operand in item["measurement"]["operands"]:
            decimal(operand["value"])
        # Keep a malformed calculation visible as unresolved instead of dropping the item.
        try:
            item["computed_quantity"] = quantity(item)
        except ValueError as exc:
            item["computed_quantity"] = None
            item["uncertainties"].append(str(exc))
    return result


def raw_page(data):
    result = deepcopy(data)
    for item in result["items"]:
        item.pop("computed_quantity", None)
    return result
