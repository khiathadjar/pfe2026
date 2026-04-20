from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from rapidfuzz import fuzz
import re

from ..base import keyword_index_collection, things_collection
from .main_localisation import compute_distance_and_room_flags, normalize_text

recherche_router = APIRouter(tags=["recherche"])


class SearchRequest(BaseModel):
    search_query: str = ""
    user_x: float = 0
    user_y: float = 0
    user_z: float = 0
    user_room: str = ""


SYNONYM_GROUPS = [
    {"light", "lights", "lamp", "lampe", "luminaire", "ampoule", "eclairage", "lighting"},
    {"printer", "imprimante", "imprim", "print"},
    {"projector", "projecteur", "videoprojecteur", "beamer"},
    {"sensor", "capteur", "detecteur", "detector"},
    {"cam", "camera", "webcam", "surveillance"},
    {"tv", "tele", "televiseur", "television", "ecran", "screen", "monitor"},
    {
        "coffee",
        "cafe",
        "cafes",
        "cafeteria",
        "cafetiere",
        "espresso",
        "nespresso",
        "percolateur",
        "coffeehouse",
    },
    {"machine", "maker", "coffeemaker", "coffeemachine", "cafemachine", "distributeur"},
    {"electromenager", "electro", "menager", "electro-menager"},
]


def _build_synonym_map() -> dict[str, set[str]]:
    synonym_map: dict[str, set[str]] = {}
    for group in SYNONYM_GROUPS:
        normalized_group = {normalize_text(term) for term in group if normalize_text(term)}
        for term in normalized_group:
            synonym_map.setdefault(term, set()).update(normalized_group)
    return synonym_map


SYNONYM_MAP = _build_synonym_map()

STATUS_VALUES = ["active", "inactive", "disponible", "en_utilisation", "indisponible", "hors-ligne", "hors ligne"]


def _tokenize_query(text: str) -> list[str]:
    # Tokenization robuste: retire ponctuation/accents et conserve uniquement les mots utiles.
    return [tok for tok in re.findall(r"[a-z0-9]+", normalize_text(text)) if len(tok) >= 2]


def _expand_tokens(tokens: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        variants = SYNONYM_MAP.get(token, {token})
        for variant in variants:
            if variant not in seen:
                expanded.append(variant)
                seen.add(variant)
    return expanded


def _extract_searchable_fields(item: dict) -> list[str]:
    res = [
        str(item.get("name", "")),
        str(item.get("type", "")),
        str(item.get("description", "")),
        str(item.get("status", "")),
        str(item.get("availability", "")),
    ]

    loc = item.get("location", "")
    if isinstance(loc, dict):
        res.append(str(loc.get("room", "")))
        res.append(str(loc.get("etage", "")))
    else:
        res.append(str(loc))
    return res


def _focus_text(item: dict) -> str:
    parts = [
        normalize_text(item.get("name", "")),
        normalize_text(item.get("type", "")),
    ]
    loc = item.get("location", {})
    if isinstance(loc, dict):
        parts.append(normalize_text(loc.get("room", "")))
    else:
        parts.append(normalize_text(str(loc)))
    return " ".join([p for p in parts if p])


def _collect_index_scores(tokens: list[str]) -> dict[str, int]:
    if not tokens:
        return {}
    docs = list(keyword_index_collection.find({"mot": {"$in": tokens}}).limit(5000))
    score_by_thing: dict[str, int] = {}
    for doc in docs:
        thing_id = str(doc.get("thingId") or "").strip()
        if not thing_id:
            continue
        weight = int(doc.get("poids") or 1)
        freq = int(doc.get("frequence") or 1)
        score_by_thing[thing_id] = score_by_thing.get(thing_id, 0) + (weight * max(1, freq))
    return score_by_thing


@recherche_router.post("/things/{thing_id}/view")
def increment_view_count(thing_id: str):
    """Enregistre une consultation d'objet et incrémente le compteur de vues."""
    try:
        thing = things_collection.find_one({"id": thing_id})
        if not thing:
            raise HTTPException(status_code=404, detail="Objet introuvable")
        
        result = things_collection.update_one(
            {"id": thing_id},
            {"$inc": {"view_count": 1}}
        )
        
        return {
            "thing_id": thing_id,
            "view_count": thing.get("view_count", 0) + 1,
            "success": result.modified_count > 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur enregistrement consultation: {e}")


@recherche_router.get("/things/suggest")
def suggest_things(q: str = ""):
    if not q or len(q.strip()) < 2:
        return []

    q_norm = normalize_text(q)
    query = {"search_name_norm": {"$regex": f"^{re.escape(q_norm)}", "$options": "i"}}
    results = list(things_collection.find(query).limit(5))
    suggestions = [item.get("name") for item in results if item.get("name")]
    return list(dict.fromkeys(suggestions))


@recherche_router.post("/things/search")
def search_things(data: SearchRequest = Body(...)):
    try:
        raw_query = (data.search_query or "").strip()

        if not raw_query:
            results = list(things_collection.find({}).sort("name", 1))
            compute_distance_and_room_flags(results, data.user_x, data.user_y, data.user_z, data.user_room)

            results.sort(key=lambda x: (
                0 if x.get("same_room") else 1,
                float(x.get("distance", 10**9)),
                -int(x.get("view_count", 0)),
                normalize_text(x.get("name", "")),
            ))

            for item in results:
                item["_id"] = str(item["_id"])
            return results

        q_norm = normalize_text(raw_query)

        matching_status = [
            s.replace("hors ligne", "hors-ligne")
            for s in STATUS_VALUES
            if normalize_text(s).startswith(q_norm)
        ]

        tokens = _tokenize_query(raw_query)
        if not tokens and q_norm:
            tokens = [q_norm]
        expanded_tokens = _expand_tokens(tokens)
        index_scores = _collect_index_scores(expanded_tokens)

        mongo_or = []
        for t in expanded_tokens:
            safe = re.escape(t)
            mongo_or.extend([
                {"search_name_norm": {"$regex": safe, "$options": "i"}},
                {"name": {"$regex": safe, "$options": "i"}},
                {"type": {"$regex": safe, "$options": "i"}},
                {"description": {"$regex": safe, "$options": "i"}},
                {"availability": {"$regex": safe, "$options": "i"}},
                {"location.room": {"$regex": safe, "$options": "i"}},
                {"location": {"$regex": safe, "$options": "i"}},
            ])

        if index_scores:
            mongo_or.append({"id": {"$in": list(index_scores.keys())}})

        for s in matching_status:
            mongo_or.append({"status": {"$regex": f"^{re.escape(s)}$", "$options": "i"}})

        pre_results = list(things_collection.find({"$or": mongo_or} if mongo_or else {}))

        filtered = []
        for item in pre_results:
            fields = _extract_searchable_fields(item)
            content_norm = " ".join(normalize_text(f) for f in fields)
            item_id = str(item.get("id", "")).strip()

            token_ok = all(
                any(term in content_norm for term in SYNONYM_MAP.get(tok, {tok}))
                for tok in tokens
            )

            status_ok = False
            if matching_status:
                item_status = normalize_text(str(item.get("status", item.get("availability", "")))).replace("hors ligne", "hors-ligne")
                status_ok = any(item_status == normalize_text(s).replace("hors ligne", "hors-ligne") for s in matching_status)

            focus = _focus_text(item)
            fuzzy_score = fuzz.partial_ratio(q_norm, focus)
            keyword_score = int(index_scores.get(item_id, 0))

            if token_ok or status_ok or fuzzy_score >= 78 or keyword_score > 0:
                item["_search_score"] = fuzzy_score + keyword_score
                filtered.append(item)

        if not filtered:
            potential = list(things_collection.find({}).limit(300))
            for item in potential:
                focus = _focus_text(item)
                score = fuzz.partial_ratio(q_norm, focus)
                if score >= 82:
                    item["_search_score"] = score
                    filtered.append(item)

        compute_distance_and_room_flags(filtered, data.user_x, data.user_y, data.user_z, data.user_room)

        filtered.sort(key=lambda x: (
            0 if x.get("same_room") else 1,
            float(x.get("distance", 10**9)),
            -int(x.get("view_count", 0)),
            -int(x.get("_search_score", 0)),
            normalize_text(x.get("name", "")),
        ))

        for item in filtered:
            item["_id"] = str(item["_id"])
            item.pop("_search_score", None)

        return filtered

    except Exception as e:
        print(f"Erreur search: {e}")
        raise HTTPException(status_code=500, detail="Erreur recherche")
