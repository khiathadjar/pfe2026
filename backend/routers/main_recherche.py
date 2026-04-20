from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from rapidfuzz import fuzz, process
import math
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
    {"light", "lights", "lamp", "lampe", "luminaire", "ampoule", "eclairage", "lighting", "lumiere", "led"},
    {"printer", "imprimante", "imprim", "print", "imprimante3d", "print3d"},
    {"projector", "projecteur", "videoprojecteur", "beamer", "projo"},
    {"sensor", "capteur", "detecteur", "detector", "probe", "sonde"},
    {"cam", "camera", "webcam", "surveillance", "cctv"},
    {"tv", "tele", "televiseur", "television", "smarttv", "ecran", "screen", "monitor", "moniteur", "display"},
    {
        "coffee",
        "cafe",
        "cafes",
        "cafeteria",
        "cafetiere",
        "cafetier",
        "espresso",
        "nespresso",
        "percolateur",
        "coffeehouse",
        "barista",
    },
    {"machine", "maker", "coffeemaker", "coffeemachine", "cafemachine", "distributeur", "dispenser"},
    {"electromenager", "electro", "menager", "electro-menager", "appliance", "device"},
]

PHRASE_TO_INTENT = {
    "machine a cafe": "coffee_machine",
    "machine cafe": "coffee_machine",
    "coffee machine": "coffee_machine",
    "coffee maker": "coffee_machine",
    "coffee maker pro": "coffee_machine",
    "cafetiere expresso": "coffee_machine",
    "cafetiere espresso": "coffee_machine",
    "machine expresso": "coffee_machine",
    "machine espresso": "coffee_machine",
    "smart tv": "television",
    "ecran tv": "television",
    "video projector": "projector",
}

INTENT_PATTERNS = {
    "coffee_machine": [
        "machine a cafe",
        "machine cafe",
        "coffee machine",
        "coffee maker",
        "coffee maker pro",
        "cafetiere",
        "coffeemaker",
        "coffeemachine",
        "espresso machine",
    ],
    "television": ["tv", "tele", "televiseur", "television", "smart tv"],
    "projector": ["projecteur", "videoprojecteur", "projector", "beamer"],
}

TOKEN_TYPO_CORRECTIONS = {
    "cofee": "coffee",
    "coffe": "coffee",
    "cofffee": "coffee",
    "caffee": "cafe",
    "cafetier": "cafetiere",
    "cafetere": "cafetiere",
    "televsion": "television",
    "televion": "television",
    "telvision": "television",
    "lamppe": "lampe",
    "projeteur": "projecteur",
    "imprimate": "imprimante",
}


def _build_synonym_map() -> dict[str, set[str]]:
    synonym_map: dict[str, set[str]] = {}
    for group in SYNONYM_GROUPS:
        normalized_group = {normalize_text(term) for term in group if normalize_text(term)}
        for term in normalized_group:
            synonym_map.setdefault(term, set()).update(normalized_group)
    return synonym_map


SYNONYM_MAP = _build_synonym_map()

STATUS_VALUES = ["active", "inactive", "disponible", "en_utilisation", "indisponible", "hors-ligne", "hors ligne"]

TERM_VOCAB = sorted(
    set(SYNONYM_MAP.keys())
    | {normalize_text(x) for x in STATUS_VALUES}
    | {"coffee", "cafe", "machine", "cafetiere", "television", "projecteur", "imprimante"}
)


def _tokenize_query(text: str) -> list[str]:
    # Tokenization robuste: retire ponctuation/accents et conserve uniquement les mots utiles.
    return [tok for tok in re.findall(r"[a-z0-9]+", normalize_text(text)) if len(tok) >= 2]


def _correct_token(token: str) -> str:
    fixed = TOKEN_TYPO_CORRECTIONS.get(token, token)
    if fixed != token:
        return fixed

    if len(token) < 4:
        return token

    best = process.extractOne(token, TERM_VOCAB, scorer=fuzz.ratio)
    if not best:
        return token

    candidate, score, _ = best
    return candidate if score >= 88 else token


def _normalize_phrase(text: str) -> str:
    return " ".join(_tokenize_query(text))


def _token_set(text: str) -> set[str]:
    return set(_tokenize_query(text))


def _pattern_matches_content(pattern: str, content_norm: str, content_tokens: set[str]) -> bool:
    pattern_norm = _normalize_phrase(pattern)
    if not pattern_norm:
        return False

    pattern_tokens = pattern_norm.split()
    if len(pattern_tokens) == 1:
        return pattern_tokens[0] in content_tokens

    return pattern_norm in content_norm


def _extract_query_intents(raw_query: str, expanded_tokens: list[str]) -> set[str]:
    intents: set[str] = set()
    phrase = _normalize_phrase(raw_query)

    for phrase_alias, intent in PHRASE_TO_INTENT.items():
        alias_norm = _normalize_phrase(phrase_alias)
        if alias_norm and alias_norm in phrase:
            intents.add(intent)

    expanded = set(expanded_tokens)
    if ({"coffee", "cafe", "cafetiere", "espresso"} & expanded) and ({"machine", "maker", "coffeemaker", "coffeemachine"} & expanded):
        intents.add("coffee_machine")

    if {"tv", "tele", "televiseur", "television", "smarttv"} & expanded:
        intents.add("television")

    if {"projecteur", "videoprojecteur", "projector", "beamer"} & expanded:
        intents.add("projector")

    return intents


def _intent_hits(content_norm: str, content_tokens: set[str], intents: set[str]) -> int:
    hits = 0
    for intent in intents:
        patterns = INTENT_PATTERNS.get(intent, [])
        if any(_pattern_matches_content(pattern, content_norm, content_tokens) for pattern in patterns):
            hits += 1
    return hits


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


def _weighted_field_score(item: dict, expanded_tokens: list[str], query_phrase_norm: str) -> int:
    name_norm = normalize_text(item.get("name", ""))
    type_norm = normalize_text(item.get("type", ""))
    desc_norm = normalize_text(item.get("description", ""))
    room_norm = normalize_text((item.get("location") or {}).get("room", "") if isinstance(item.get("location"), dict) else item.get("location", ""))

    name_tokens = _token_set(name_norm)
    type_tokens = _token_set(type_norm)
    desc_tokens = _token_set(desc_norm)
    room_tokens = _token_set(room_norm)

    score = 0

    for token in expanded_tokens:
        if token in name_tokens:
            score += 14
        if token in type_tokens:
            score += 9
        if token in room_tokens:
            score += 7
        if token in desc_tokens:
            score += 3

    if query_phrase_norm and query_phrase_norm in name_norm:
        score += 45
    elif query_phrase_norm and query_phrase_norm in f"{name_norm} {type_norm}":
        score += 20

    return score


def _compute_adaptive_score(
    item: dict,
    *,
    q_norm: str,
    tokens: list[str],
    expanded_tokens: list[str],
    keyword_score: int,
    fuzzy_score: int,
    content_norm: str,
    query_intents: set[str],
) -> int:
    content_tokens = _token_set(content_norm)
    matched_tokens = 0
    for tok in tokens:
        variants = SYNONYM_MAP.get(tok, {tok})
        if any(variant in content_tokens for variant in variants):
            matched_tokens += 1

    token_coverage = matched_tokens / max(1, len(tokens))
    intent_score = _intent_hits(content_norm, content_tokens, query_intents) * 20
    field_score = _weighted_field_score(item, expanded_tokens, q_norm)

    views = max(0, int(item.get("view_count", 0)))
    popularity_score = min(18, int(round(math.log1p(views) * 4)))

    total = (
        int(fuzzy_score)
        + int(keyword_score)
        + int(round(token_coverage * 30))
        + int(intent_score)
        + int(field_score)
        + int(popularity_score)
    )
    return total


def _search_logic(data: SearchRequest) -> list[dict]:
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
    tokens = [_correct_token(tok) for tok in tokens]

    expanded_tokens = _expand_tokens(tokens)
    query_intents = _extract_query_intents(raw_query, expanded_tokens)
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

    for intent in query_intents:
        for pattern in INTENT_PATTERNS.get(intent, []):
            safe_pattern = re.escape(_normalize_phrase(pattern))
            if safe_pattern:
                mongo_or.extend([
                    {"search_name_norm": {"$regex": safe_pattern, "$options": "i"}},
                    {"name": {"$regex": safe_pattern, "$options": "i"}},
                    {"type": {"$regex": safe_pattern, "$options": "i"}},
                    {"description": {"$regex": safe_pattern, "$options": "i"}},
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
        content_tokens = _token_set(content_norm)
        item_id = str(item.get("id", "")).strip()

        token_ok = all(
            any(term in content_tokens for term in SYNONYM_MAP.get(tok, {tok}))
            for tok in tokens
        )

        status_ok = False
        if matching_status:
            item_status = normalize_text(str(item.get("status", item.get("availability", "")))).replace("hors ligne", "hors-ligne")
            status_ok = any(item_status == normalize_text(s).replace("hors ligne", "hors-ligne") for s in matching_status)

        focus = _focus_text(item)
        fuzzy_score = int(fuzz.partial_ratio(q_norm, focus))
        keyword_score = int(index_scores.get(item_id, 0))
        intent_match_count = _intent_hits(content_norm, content_tokens, query_intents)

        should_keep = token_ok or status_ok or fuzzy_score >= 74 or keyword_score > 0 or intent_match_count > 0
        if should_keep:
            item["_search_score"] = _compute_adaptive_score(
                item,
                q_norm=q_norm,
                tokens=tokens,
                expanded_tokens=expanded_tokens,
                keyword_score=keyword_score,
                fuzzy_score=fuzzy_score,
                content_norm=content_norm,
                query_intents=query_intents,
            )
            filtered.append(item)

    if not filtered:
        potential = list(things_collection.find({}).limit(400))
        for item in potential:
            focus = _focus_text(item)
            score = int(fuzz.partial_ratio(q_norm, focus))
            if score >= 80:
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


class SearchBenchmarkCase(BaseModel):
    query: str
    expected_ids: list[str]
    user_x: float = 0
    user_y: float = 0
    user_z: float = 0
    user_room: str = ""


class SearchBenchmarkRequest(BaseModel):
    cases: list[SearchBenchmarkCase]
    k: int = 5


@recherche_router.post("/things/search/benchmark")
def benchmark_search(data: SearchBenchmarkRequest = Body(...)):
    """
    Endpoint de metriques formelles (Precision@K, Recall@K, MRR).
    """
    if not data.cases:
        return {
            "precision_at_k": 0.0,
            "recall_at_k": 0.0,
            "mrr_at_k": 0.0,
            "evaluated_cases": 0,
            "k": max(1, int(data.k or 5)),
            "details": [],
        }

    k = max(1, int(data.k or 5))
    precisions = []
    recalls = []
    mrrs = []
    details = []

    for case in data.cases:
        search_payload = SearchRequest(
            search_query=case.query,
            user_x=case.user_x,
            user_y=case.user_y,
            user_z=case.user_z,
            user_room=case.user_room,
        )
        results = _search_logic(search_payload)
        top_ids = [str(r.get("id", "")).strip() for r in results[:k] if str(r.get("id", "")).strip()]
        expected = {str(x).strip() for x in case.expected_ids if str(x).strip()}

        if not expected:
            continue

        hits = sum(1 for rid in top_ids if rid in expected)
        precision = hits / float(k)
        recall = hits / float(len(expected))

        rr = 0.0
        for idx, rid in enumerate(top_ids, start=1):
            if rid in expected:
                rr = 1.0 / float(idx)
                break

        precisions.append(precision)
        recalls.append(recall)
        mrrs.append(rr)
        details.append(
            {
                "query": case.query,
                "top_ids": top_ids,
                "expected_ids": sorted(expected),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "reciprocal_rank": round(rr, 4),
            }
        )

    evaluated = len(precisions)
    if evaluated == 0:
        return {
            "precision_at_k": 0.0,
            "recall_at_k": 0.0,
            "mrr_at_k": 0.0,
            "evaluated_cases": 0,
            "k": k,
            "details": details,
        }

    return {
        "precision_at_k": round(sum(precisions) / evaluated, 4),
        "recall_at_k": round(sum(recalls) / evaluated, 4),
        "mrr_at_k": round(sum(mrrs) / evaluated, 4),
        "evaluated_cases": evaluated,
        "k": k,
        "details": details,
    }


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
        return _search_logic(data)

    except Exception as e:
        print(f"Erreur search: {e}")
        raise HTTPException(status_code=500, detail="Erreur recherche")
