from __future__ import annotations

import re


WASTE_MATERIAL_SYNONYMS = {
    "plastic": (
        "plastic",
        "plastic bottle",
        "plastic bottles",
        "plastic packaging",
        "plastic waste",
    ),
    "cardboard": ("cardboard", "cardboard box", "cardboard boxes"),
    "paper": ("paper", "paper waste"),
    "glass": ("glass", "glass bottle", "glass bottles"),
    "metal": ("metal", "can", "cans", "aluminium can", "aluminium cans", "steel can"),
    "food_waste": (
        "food scraps",
        "food scrap",
        "food waste",
        "organic waste",
        "leftover food",
        "leftover food scraps",
        "food leftovers",
    ),
    "mixed_packaging": (
        "mixed packaging",
        "packaging",
        "packaging waste",
        "food packaging",
        "food packaging waste",
        "wrappers",
        "wrapper",
    ),
    "general_waste": (
        "general rubbish",
        "general waste",
        "municipal solid waste",
        "solid waste",
        "mixed municipal waste",
        "msw",
        "rubbish",
        "garbage",
        "trash",
    ),
}

WASTE_DISPOSAL_METHOD_SYNONYMS = {
    "landfill": (
        "landfill",
        "landfill bin",
        "general rubbish",
        "general waste",
        "threw away",
        "throw away",
        "thrown away",
        "discarded",
        "discard",
        "disposed of",
        "rubbish bin",
        "garbage bin",
        "trash bin",
    ),
    "recycling": ("recycled", "recycle", "recycling", "recycling bin"),
    "composting": ("composted", "compost", "composting", "compost bin"),
    "incineration": ("incinerated", "incineration", "burned", "burnt"),
}

BROADER_WASTE_MATERIALS = {
    "plastic": ("general_waste", "mixed_packaging"),
    "cardboard": ("general_waste", "mixed_packaging"),
    "paper": ("general_waste", "mixed_packaging"),
    "glass": ("general_waste", "mixed_packaging"),
    "metal": ("general_waste", "mixed_packaging"),
    "food_waste": ("general_waste",),
    "mixed_packaging": ("general_waste",),
}


def detect_waste_material_classes(text: str) -> set[str]:
    normalized = _normalized_text(text)
    matches = {
        material_class
        for material_class, synonyms in WASTE_MATERIAL_SYNONYMS.items()
        if any(_contains_phrase(normalized, synonym) for synonym in synonyms)
    }
    if "mixed_packaging" in matches and "plastic" in matches:
        if _contains_phrase(normalized, "plastic packaging"):
            matches.discard("mixed_packaging")
    return matches


def normalize_waste_material(value: object, evidence_text: str = "") -> str | None:
    proposed = _normalized_token(value)
    if not proposed:
        return None
    if proposed in WASTE_MATERIAL_SYNONYMS:
        return proposed
    evidence = f"{evidence_text} {proposed}".strip()
    matches = detect_waste_material_classes(evidence)
    return next(iter(matches)) if len(matches) == 1 else None


def detect_waste_disposal_method(text: str) -> str | None:
    normalized = _normalized_text(text)
    for method, synonyms in WASTE_DISPOSAL_METHOD_SYNONYMS.items():
        if any(_contains_phrase(normalized, synonym) for synonym in synonyms):
            return method
    return None


def method_conflicts(requested_method: str, text: str) -> str | None:
    detected = detect_waste_disposal_method(text)
    if detected and detected != requested_method:
        return detected
    return None


def material_conflicts(requested_material: str, text: str) -> str | None:
    detected = detect_waste_material_classes(text)
    if not detected:
        return None
    if requested_material in detected:
        return None
    broader = set(BROADER_WASTE_MATERIALS.get(requested_material, ()))
    if broader.intersection(detected):
        return None
    return sorted(detected)[0]


def material_matches(requested_material: str, text: str) -> bool:
    return requested_material in detect_waste_material_classes(text)


def material_is_broader_match(requested_material: str, text: str) -> bool:
    detected = detect_waste_material_classes(text)
    return bool(set(BROADER_WASTE_MATERIALS.get(requested_material, ())).intersection(detected))


def method_matches(requested_method: str, text: str) -> bool:
    return detect_waste_disposal_method(text) == requested_method


def ontology_terms(*values: str) -> list[str]:
    terms: list[str] = []
    for value in values:
        if value in WASTE_MATERIAL_SYNONYMS:
            terms.extend(WASTE_MATERIAL_SYNONYMS[value])
        if value in WASTE_DISPOSAL_METHOD_SYNONYMS:
            terms.extend(WASTE_DISPOSAL_METHOD_SYNONYMS[value])
    return list(dict.fromkeys(terms))


def _contains_phrase(normalized_text: str, phrase: str) -> bool:
    normalized_phrase = _normalized_text(phrase)
    return bool(normalized_phrase and f" {normalized_phrase} " in f" {normalized_text} ")


def _normalized_text(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _normalized_token(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")
