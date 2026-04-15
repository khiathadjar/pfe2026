import re
import sys
import unicodedata
import uuid

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field

from ..base import keyword_index_collection, things_collection
from .main_auth import require_admin
from .main_localisation import canonical_room_name as _canonical_room_name, coords_from_room as _coords_from_room
from ..notifications_service import create_notification

crud_router = APIRouter(tags=["crud"])


class AddThingRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    type: str = Field(..., min_length=1, max_length=80)
    location: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=800)
    status: str = Field(default="active", max_length=40)
    endpoint_url: str = Field(default="", max_length=300)


class UpdateThingRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    type: str = Field(..., min_length=1, max_length=80)
    location: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=800)
    status: str = Field(default="active", max_length=40)
    endpoint_url: str = Field(default="", max_length=300)


def _main_module():
    return sys.modules.get("main")


def _things_collection():
    module = _main_module()
    return getattr(module, "things_collection", things_collection) if module else things_collection


def _index_collection():
    module = _main_module()
    if module is not None:
        return getattr(module, "index_mot_cle_collection", getattr(module, "keyword_index_collection", keyword_index_collection))
    return keyword_index_collection


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text


def _canonical_availability(status: str) -> str:
    s = _normalize_text(status)
    if s in {"active", "disponible", "in-stock", "instock"}:
        return "disponible"
    if s in {"en_utilisation", "en utilisation", "borrowed"}:
        return "en_utilisation"
    return "indisponible"


def _clean_endpoint_url(endpoint_url: str) -> str:
    clean = str(endpoint_url or "").strip()
    if not clean:
        return ""
    if not re.match(r"^https?://", clean, flags=re.IGNORECASE):
        raise HTTPException(status_code=400, detail="Endpoint reseau invalide")
    return clean.rstrip("/")


def _build_remote_control(endpoint_url: str) -> dict | None:
    endpoint = _clean_endpoint_url(endpoint_url)
    if not endpoint:
        return None

    on_href = f"{endpoint}/actions/on"
    off_href = f"{endpoint}/actions/off"
    return {
        "@type": "EntryPoint",
        "name": "REST Control",
        "protocol": "REST",
        "contentType": "application/json",
        "endpoint": endpoint,
        "health": f"{endpoint}/health",
        "actions": {
            "on": {"method": "POST", "href": on_href},
            "off": {"method": "POST", "href": off_href},
        },
    }


def _build_potential_actions(endpoint_url: str) -> list[dict]:
    endpoint = _clean_endpoint_url(endpoint_url)
    if not endpoint:
        return []

    return [
        {
            "@type": "ActivateAction",
            "name": "on",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"{endpoint}/actions/on",
                "httpMethod": "POST",
                "contentType": "application/json",
            },
        },
        {
            "@type": "DeactivateAction",
            "name": "off",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"{endpoint}/actions/off",
                "httpMethod": "POST",
                "contentType": "application/json",
            },
        },
    ]


def _to_index_id(thing_id: str) -> int:
    try:
        return int((thing_id or "").replace("-", "")[:8], 16)
    except Exception:
        return 0


def _extract_keywords(text: str) -> list[str]:
    norm = _normalize_text(text)
    return re.findall(r"[a-z0-9]+", norm)


def _build_keyword_docs(item: dict) -> list[dict]:
    thing_id = str(item.get("id", "")).strip()
    fields = [
        ("TITRE", 3, item.get("name", "")),
        ("TYPE", 2, item.get("type", "")),
        ("DESCRIPTION", 1, item.get("description", "")),
        ("SALLE", 2, (item.get("location") or {}).get("room", "") if isinstance(item.get("location"), dict) else ""),
    ]

    frequency: dict[tuple[str, str], int] = {}
    for source, weight, text in fields:
        for token in _extract_keywords(str(text or "")):
            key = (token, source)
            frequency[key] = frequency.get(key, 0) + 1

    docs = []
    for (token, source), freq in frequency.items():
        docs.append(
            {
                "mot": token,
                "thingId": thing_id,
                "poids": 3 if source == "TITRE" else (2 if source in {"TYPE", "SALLE"} else 1),
                "source": source,
                "frequence": max(1, int(freq)),
            }
        )
    return docs


def _reindex_thing(item: dict) -> None:
    thing_id = str(item.get("id", "")).strip()
    if not thing_id:
        return
    index_collection = _index_collection()
    index_collection.delete_many({"thingId": thing_id})
    docs = _build_keyword_docs(item)
    if docs:
        index_collection.insert_many(docs)


@crud_router.post("/things/add")
def add_thing(request: Request, data: AddThingRequest = Body(...)):
    require_admin(request)
    try:
        location_room = _canonical_room_name(data.location.strip())
        coords = _coords_from_room(location_room)
        availability = _canonical_availability(data.status)
        remote_control = _build_remote_control(data.endpoint_url)
        potential_actions = _build_potential_actions(data.endpoint_url)

        new_item = {
            "@context": "https://schema.org",
            "@type": "Product",
            "id": str(uuid.uuid4())[:8],
            "name": data.name,
            "search_name_norm": _normalize_text(data.name),
            "type": data.type,
            "description": data.description,
            "status": data.status,
            "availability": availability,
            "view_count": 0,
            "location": {
                "@type": "Place",
                "name": location_room,
                "room": location_room,
                "x": coords["x"],
                "y": coords["y"],
                "z": coords["z"],
            },
        }

        if remote_control:
            new_item["control"] = remote_control
            new_item["device_state"] = {
                "power": "off",
                "last_action_at": "",
                "reachable": True,
            }
            if potential_actions:
                new_item["potentialAction"] = potential_actions

        _things_collection().insert_one(new_item)
        _reindex_thing(new_item)
        create_notification(
            target_role="admin",
            title="Objet ajoute",
            message=f"Objet ajoute: {new_item['name']} ({new_item['id']}).",
            notif_type="success",
            metadata={"thing_id": new_item["id"], "action": "add"},
        )
        return {"message": "Succes", "id": new_item["id"]}
    except Exception as e:
        print(f"Erreur add: {e}")
        raise HTTPException(status_code=500, detail="Erreur MongoDB")


@crud_router.get("/things/{thing_id}")
def get_thing(thing_id: str):
    try:
        thing = _things_collection().find_one({"id": thing_id})
        if not thing:
            raise HTTPException(status_code=404, detail="Objet non trouvé")

        thing["id"] = str(thing.get("id", thing_id))
        if "_id" in thing:
            thing["_id"] = str(thing["_id"])

        return thing
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erreur get thing: {e}")
        raise HTTPException(status_code=500, detail="Erreur MongoDB")


@crud_router.patch("/things/{thing_id}/status")
def update_thing_status(thing_id: str, data: dict = Body(...)):
    """Met à jour le statut et la disponibilité d'un objet."""
    try:
        new_status = data.get("status", "").strip()
        if not new_status:
            raise HTTPException(status_code=400, detail="Status requis")
        
        things = _things_collection()
        
        # Mettre à jour le statut et la disponibilité
        result = things.find_one_and_update(
            {"id": thing_id},
            {
                "$set": {
                    "status": new_status,
                    "availability": _canonical_availability(new_status)
                }
            },
            return_document=True
        )
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Objet '{thing_id}' non trouvé")
        
        # Réindexer après modification
        _reindex_thing(result)
        create_notification(
            target_role="admin",
            title="Statut objet modifie",
            message=f"Statut de {result.get('name', thing_id)} change en {new_status}.",
            notif_type="info",
            metadata={"thing_id": thing_id, "action": "status", "status": new_status},
        )
        
        return {
            "success": True,
            "message": f"Statut changé en '{new_status}'",
            "thing": {
                "id": result.get("id"),
                "name": result.get("name"),
                "status": result.get("status"),
                "availability": result.get("availability")
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erreur update status: {e}")
        raise HTTPException(status_code=500, detail="Erreur MongoDB")


@crud_router.put("/things/{thing_id}")
def update_thing(thing_id: str, request: Request, data: UpdateThingRequest = Body(...)):
    require_admin(request)
    try:
        things = _things_collection()
        existing = things.find_one({"id": thing_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Objet non trouvé")

        location_room = _canonical_room_name(data.location.strip())
        coords = _coords_from_room(location_room)
        availability = _canonical_availability(data.status)
        remote_control = _build_remote_control(data.endpoint_url)
        potential_actions = _build_potential_actions(data.endpoint_url)

        updated_fields = {
            "name": data.name,
            "search_name_norm": _normalize_text(data.name),
            "type": data.type,
            "description": data.description,
            "status": data.status,
            "availability": availability,
            "location": {
                "@type": "Place",
                "name": location_room,
                "room": location_room,
                "x": coords["x"],
                "y": coords["y"],
                "z": coords["z"],
            },
        }

        unset_fields = {}
        if remote_control:
            previous_state = existing.get("device_state") if isinstance(existing.get("device_state"), dict) else {}
            updated_fields["control"] = remote_control
            updated_fields["device_state"] = {
                "power": str(previous_state.get("power") or "off").lower() == "on" and "on" or "off",
                "last_action_at": str(previous_state.get("last_action_at") or ""),
                "reachable": bool(previous_state.get("reachable", True)),
            }
            if potential_actions:
                updated_fields["potentialAction"] = potential_actions
        else:
            unset_fields["control"] = ""
            unset_fields["device_state"] = ""
            unset_fields["potentialAction"] = ""

        update_doc = {"$set": updated_fields}
        if unset_fields:
            update_doc["$unset"] = unset_fields

        thing = things.find_one_and_update(
            {"id": thing_id},
            update_doc,
            return_document=True,
        )

        thing["id"] = thing_id
        if "_id" in thing:
            thing["_id"] = str(thing["_id"])
        _reindex_thing(thing)
        create_notification(
            target_role="admin",
            title="Objet modifie",
            message=f"Objet modifie: {thing.get('name', thing_id)} ({thing_id}).",
            notif_type="info",
            metadata={"thing_id": thing_id, "action": "update"},
        )
        return {"success": True, "message": "Objet modifié", "thing": thing}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erreur update thing: {e}")
        raise HTTPException(status_code=500, detail="Erreur MongoDB")


def _cleanup_orphan_keywords() -> int:
    """Supprime tous les mots-clés orphelins (dont le thingId n'existe plus)."""
    things = _things_collection()
    index_collection = _index_collection()
    
    # Récupérer tous les thingId uniques dans keyword_index
    orphan_thing_ids = []
    try:
        all_keyword_thing_ids = list(index_collection.distinct("thingId"))
        
        # Pour chaque thingId, vérifier s'il existe dans things
        for thing_id in all_keyword_thing_ids:
            if not things.find_one({"id": str(thing_id).strip()}):
                orphan_thing_ids.append(str(thing_id).strip())
        
        # Supprimer tous les mots-clés orphelins
        if orphan_thing_ids:
            result = index_collection.delete_many({"thingId": {"$in": orphan_thing_ids}})
            return result.deleted_count
    except Exception as e:
        print(f"Erreur cleanup keywords: {e}")
    
    return 0


@crud_router.delete("/things/{thing_id}")
def delete_thing(thing_id: str, request: Request):
    require_admin(request)
    things = _things_collection()
    thing_id_clean = str(thing_id).strip()
    
    if things.delete_one({"id": thing_id_clean}).deleted_count == 0:
        raise HTTPException(status_code=404, detail="Non trouve")
    
    # Supprimer tous les mots-clés associés à cet objet
    index_collection = _index_collection()
    deleted_keywords = index_collection.delete_many({"thingId": thing_id_clean}).deleted_count
    
    # Nettoyer aussi les mots-clés orphelins si besoin
    orphain_count = _cleanup_orphan_keywords()
    
    create_notification(
        target_role="admin",
        title="Objet supprime",
        message=f"Objet supprime: {thing_id}. {deleted_keywords} mots-cles supprimes.",
        notif_type="warning",
        metadata={"thing_id": thing_id, "action": "delete", "keywords_deleted": deleted_keywords, "orphans_cleaned": orphain_count},
    )
    return {"success": True, "keywords_deleted": deleted_keywords, "orphans_cleaned": orphain_count}


@crud_router.post("/maintenance/cleanup-orphan-keywords")
def cleanup_orphan_keywords_endpoint(request: Request):
    """Endpoint de maintenance pour nettoyer les mots-clés orphelins."""
    require_admin(request)
    
    cleaned_count = _cleanup_orphan_keywords()
    
    create_notification(
        target_role="admin",
        title="Maintenance: Nettoyage des mots-clés",
        message=f"{cleaned_count} mots-clés orphelins supprimes.",
        notif_type="info",
        metadata={"action": "cleanup_keywords", "count": cleaned_count},
    )
    
    return {"success": True, "orphan_keywords_deleted": cleaned_count}
