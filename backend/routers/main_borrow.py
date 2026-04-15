from datetime import datetime, timezone
import sys

import requests
from fastapi import APIRouter, HTTPException, Request

from ..base import things_collection, user_history_collection
from .main_auth import _get_user_from_token, _prune_user_history, extract_bearer_token
from ..notifications_service import create_notification

borrow_router = APIRouter(tags=["borrow"])


def _main_module():
    return sys.modules.get("main")


def _things_collection():
    module = _main_module()
    return getattr(module, "things_collection", things_collection) if module else things_collection


def _user_history_collection():
    module = _main_module()
    return getattr(module, "user_history_collection", user_history_collection) if module else user_history_collection


def _auth_user_checker():
    module = _main_module()
    return getattr(module, "_require_authenticated_user", None) if module else None


def _normalize_text(text: str) -> str:
    return str(text or "").strip().lower()


def _canonical_availability(status: str) -> str:
    s = _normalize_text(status)
    if s in {"active", "disponible", "in-stock", "instock"}:
        return "disponible"
    if s in {"en_utilisation", "en utilisation", "borrowed"}:
        return "en_utilisation"
    return "indisponible"


def _require_authenticated_user(request: Request) -> tuple[str, str]:
    main_checker = _auth_user_checker()
    if callable(main_checker) and main_checker is not _require_authenticated_user:
        return main_checker(request)

    token = extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Token manquant")

    user = _get_user_from_token(token)

    return str(user.id), str(getattr(user, "email", "") or "")


def _active_borrow_log(history, user_id: str, thing_id: str):
    return history.find_one(
        {
            "thing_id": thing_id,
            "user_id": user_id,
            "action": "EMPRUNT_DEBUT",
            "returned": False,
        },
        sort=[("created_at", -1)],
    )


def _remote_action_config(thing: dict, action_name: str) -> dict:
    control = thing.get("control") if isinstance(thing.get("control"), dict) else {}
    actions = control.get("actions") if isinstance(control.get("actions"), dict) else {}
    action_cfg = actions.get(action_name) if isinstance(actions.get(action_name), dict) else {}
    href = str(action_cfg.get("href") or "").strip()
    method = str(action_cfg.get("method") or "POST").strip().upper()
    if not href:
        raise HTTPException(status_code=400, detail="Aucune action distante configuree pour cet objet")
    return {"href": href, "method": method}


@borrow_router.get("/user/mes-objets")
def get_mes_objets(request: Request):
    user_id, _ = _require_authenticated_user(request)
    history = _user_history_collection()
    things = _things_collection()

    open_logs = list(
        history.find(
            {
                "user_id": user_id,
                "action": "EMPRUNT_DEBUT",
                "returned": False,
            }
        ).sort("created_at", -1)
    )

    result = []
    for log in open_logs:
        thing_id = str(log.get("thing_id") or "").strip()
        if not thing_id:
            continue

        thing = things.find_one({"id": thing_id}) or {}
        loc = thing.get("location") if isinstance(thing.get("location"), dict) else {}

        result.append(
            {
                "thing_id": thing_id,
                "name": thing.get("name") or log.get("thing_name") or "Objet",
                "type": thing.get("type") or thing.get("@type") or "-",
                "status": thing.get("status") or "inactive",
                "availability": thing.get("availability") or "en_utilisation",
                "location": {
                    "room": loc.get("room") or loc.get("name") or log.get("salle") or "-",
                    "x": loc.get("x", 0),
                    "y": loc.get("y", 0),
                    "z": loc.get("z", 0),
                },
                "taken_at": log.get("created_at") or "",
                "control": thing.get("control") if isinstance(thing.get("control"), dict) else None,
                "device_state": thing.get("device_state") if isinstance(thing.get("device_state"), dict) else {},
            }
        )

    return result


@borrow_router.post("/things/{thing_id}/prendre")
@borrow_router.post("/take/{thing_id}")
def prendre_objet(thing_id: str, request: Request):
    user_id, email = _require_authenticated_user(request)

    things = _things_collection()
    history = _user_history_collection()

    thing = things.find_one({"id": thing_id})
    if not thing:
        raise HTTPException(status_code=404, detail="Objet introuvable")

    availability = _canonical_availability(str(thing.get("availability") or thing.get("status") or ""))
    if availability != "disponible":
        raise HTTPException(status_code=400, detail="Objet non disponible")

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    room_name = ""
    loc = thing.get("location")
    if isinstance(loc, dict):
        room_name = str(loc.get("room") or loc.get("name") or "")

    history.insert_one(
        {
            "user_id": user_id,
            "email": email,
            "action": "EMPRUNT_DEBUT",
            "detail": f"Prise de {thing.get('name', 'objet')}",
            "status": "en_utilisation",
            "date": now.strftime("%d/%m/%Y %H:%M:%S"),
            "created_at": now_iso,
            "thing_id": thing_id,
            "thing_name": thing.get("name", ""),
            "salle": room_name,
            "returned": False,
        }
    )
    _prune_user_history(user_id)

    things.update_one(
        {"id": thing_id},
        {"$set": {"availability": "en_utilisation", "status": "inactive"}},
    )

    thing_name = str(thing.get("name") or "objet")
    create_notification(
        target_role="user",
        recipient_user_id=user_id,
        recipient_email=email,
        actor_user_id=user_id,
        actor_email=email,
        title="Objet pris",
        message=f"Vous avez pris {thing_name}.",
        notif_type="success",
        metadata={"thing_id": thing_id, "action": "take"},
    )
    create_notification(
        target_role="admin",
        actor_user_id=user_id,
        actor_email=email,
        title="Emprunt utilisateur",
        message=f"{email or user_id} a pris {thing_name}.",
        notif_type="info",
        metadata={"thing_id": thing_id, "action": "take", "user_id": user_id},
    )

    return {
        "success": True,
        "message": f"Vous avez pris {thing.get('name', 'objet')}",
        "timestamp": now_iso,
    }


@borrow_router.post("/things/{thing_id}/retourner")
@borrow_router.post("/return/{thing_id}")
def retourner_objet(thing_id: str, request: Request):
    user_id, email = _require_authenticated_user(request)

    things = _things_collection()
    history = _user_history_collection()

    open_log = _active_borrow_log(history, user_id, thing_id)
    if not open_log:
        raise HTTPException(status_code=400, detail="Aucun emprunt actif pour cet objet")

    start_raw = open_log.get("created_at")
    try:
        start_dt = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
    except Exception:
        start_dt = datetime.now(timezone.utc)

    end_dt = datetime.now(timezone.utc)
    duration_min = max(0, int((end_dt - start_dt).total_seconds() // 60))

    history.update_one(
        {"_id": open_log["_id"]},
        {
            "$set": {
                "returned": True,
                "returned_at": end_dt.isoformat(),
                "duree_minutes": duration_min,
            }
        },
    )

    thing = things.find_one({"id": thing_id}) or {}
    history.insert_one(
        {
            "user_id": user_id,
            "email": email,
            "action": "EMPRUNT_FIN",
            "detail": f"Retour de {thing.get('name', 'objet')}",
            "status": "disponible",
            "date": end_dt.strftime("%d/%m/%Y %H:%M:%S"),
            "created_at": end_dt.isoformat(),
            "thing_id": thing_id,
            "thing_name": thing.get("name", ""),
            "duree_minutes": duration_min,
        }
    )
    _prune_user_history(user_id)

    things.update_one(
        {"id": thing_id},
        {"$set": {"availability": "disponible", "status": "active"}},
    )

    thing_name = str(thing.get("name") or "objet")
    create_notification(
        target_role="user",
        recipient_user_id=user_id,
        recipient_email=email,
        actor_user_id=user_id,
        actor_email=email,
        title="Objet retourne",
        message=f"Vous avez retourne {thing_name}.",
        notif_type="success",
        metadata={"thing_id": thing_id, "action": "return", "duration_min": duration_min},
    )
    create_notification(
        target_role="admin",
        actor_user_id=user_id,
        actor_email=email,
        title="Retour utilisateur",
        message=f"{email or user_id} a retourne {thing_name} ({duration_min} min).",
        notif_type="info",
        metadata={"thing_id": thing_id, "action": "return", "duration_min": duration_min, "user_id": user_id},
    )

    return {
        "success": True,
        "message": f"Merci. Objet retourne apres {duration_min} minutes",
        "duree_minutes": duration_min,
    }


@borrow_router.post("/things/{thing_id}/actions/{action_name}")
def trigger_remote_object_action(thing_id: str, action_name: str, request: Request):
    user_id, email = _require_authenticated_user(request)

    safe_action = str(action_name or "").strip().lower()
    if safe_action not in {"on", "off"}:
        raise HTTPException(status_code=400, detail="Action distante non supportee")

    things = _things_collection()
    history = _user_history_collection()

    open_log = _active_borrow_log(history, user_id, thing_id)
    if not open_log:
        raise HTTPException(status_code=403, detail="Vous devez prendre cet objet avant de l'utiliser")

    thing = things.find_one({"id": thing_id})
    if not thing:
        raise HTTPException(status_code=404, detail="Objet introuvable")

    remote_cfg = _remote_action_config(thing, safe_action)

    # Premier essai: appel selon la configuration fournie
    last_exception = None
    remote_response = None
    try:
        remote_response = requests.request(remote_cfg["method"], remote_cfg["href"], timeout=6)
    except requests.RequestException as exc:
        last_exception = exc

    # Si l'appel initial a echoue ou retourne une erreur, tenter quelques fallbacks courants
    if not remote_response or not getattr(remote_response, "ok", False):
        # tentatives alternatives: même method avec JSON, POST avec different payloads, puis GET
        try:
            resp_alt = requests.request(remote_cfg["method"], remote_cfg["href"], json={"action": safe_action}, timeout=6)
            if getattr(resp_alt, "ok", False):
                remote_response = resp_alt
        except requests.RequestException as exc2:
            last_exception = exc2

        if not remote_response or not getattr(remote_response, "ok", False):
            for body in ({"state": safe_action}, {"power": safe_action}):
                try:
                    resp_alt = requests.post(remote_cfg["href"], json=body, timeout=6)
                    if getattr(resp_alt, "ok", False):
                        remote_response = resp_alt
                        break
                except requests.RequestException as exc3:
                    last_exception = exc3

        if not remote_response or not getattr(remote_response, "ok", False):
            try:
                resp_alt = requests.get(remote_cfg["href"], timeout=6)
                if getattr(resp_alt, "ok", False):
                    remote_response = resp_alt
            except requests.RequestException as exc4:
                last_exception = exc4

    if not remote_response:
        things.update_one(
            {"id": thing_id},
            {"$set": {"device_state.reachable": False}},
        )
        raise HTTPException(status_code=502, detail=f"Objet distant injoignable: {last_exception}") from last_exception

    try:
        payload = remote_response.json()
    except ValueError:
        payload = {"message": remote_response.text.strip()}

    if not getattr(remote_response, "ok", False):
        detail = payload.get("detail") or payload.get("error") or payload.get("message") or "Echec action distante"
        raise HTTPException(status_code=502, detail=str(detail))

    now_iso = datetime.now(timezone.utc).isoformat()
    power_state = "on" if safe_action == "on" else "off"
    device_state = {
        "power": power_state,
        "last_action_at": now_iso,
        "reachable": True,
        "last_result": payload,
    }

    things.update_one(
        {"id": thing_id},
        {"$set": {"device_state": device_state}},
    )

    history.insert_one(
        {
            "user_id": user_id,
            "email": email,
            "action": "OBJET_ACTION",
            "detail": f"{thing.get('name', 'objet')} -> {safe_action.upper()}",
            "status": "Succes",
            "date": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S"),
            "created_at": now_iso,
            "thing_id": thing_id,
            "thing_name": thing.get("name", ""),
        }
    )
    _prune_user_history(user_id)

    thing_name = str(thing.get("name") or "objet")
    create_notification(
        target_role="user",
        recipient_user_id=user_id,
        recipient_email=email,
        actor_user_id=user_id,
        actor_email=email,
        title="Commande objet executee",
        message=f"Action {safe_action.upper()} envoyee a {thing_name}.",
        notif_type="success",
        metadata={"thing_id": thing_id, "action": safe_action},
    )

    return {
        "success": True,
        "message": payload.get("message") or f"Action {safe_action.upper()} executee",
        "thing_id": thing_id,
        "device_state": device_state,
        "remote_response": payload,
    }
