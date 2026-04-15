from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import APIRouter, Request, Body, HTTPException
from pydantic import BaseModel, Field

from ..base import devices_collection
from .main_auth import extract_bearer_token, _get_user_from_token, require_admin


devices_router = APIRouter()


class DeviceRegisterRequest(BaseModel):
    device_id: Optional[str] = Field(default=None, max_length=200)
    ip: Optional[str] = Field(default=None, max_length=64)
    hostname: Optional[str] = Field(default="", max_length=200)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


@devices_router.post("/devices/register")
def register_device(request: Request, data: DeviceRegisterRequest = Body(...)):
    """Register or update a device (phone) IP. Optional bearer token associates the device with a user."""
    token = extract_bearer_token(request)
    user_id = None
    user_email = ""
    if token:
        try:
            user = _get_user_from_token(token)
            user_id = str(user.id)
            user_email = getattr(user, "email", "") or ""
        except HTTPException:
            # Token invalid -> ignore and allow anonymous registration
            user_id = None
        except Exception:
            user_id = None

    ip = (data.ip or (request.client.host if getattr(request, "client", None) else None) or "").strip()
    device_id = str(data.device_id).strip() if data.device_id else None
    hostname = str(data.hostname or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not device_id and not ip:
        raise HTTPException(status_code=400, detail="device_id ou ip requis")

    query = {"device_id": device_id} if device_id else {"ip": ip}

    update_doc = {
        "$set": {
            "device_id": device_id,
            "ip": ip,
            "hostname": hostname,
            "user_id": user_id,
            "email": user_email,
            "metadata": data.metadata or {},
            "last_seen": now_iso,
        },
        "$setOnInsert": {"created_at": now_iso},
    }

    try:
        devices_collection.update_one(query, update_doc, upsert=True)
        doc = devices_collection.find_one(query)
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return {"success": True, "device": doc}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur enregistrement: {e}")


@devices_router.get("/admin/devices")
def list_devices(request: Request, limit: int = 200):
    """Admin: list registered devices."""
    require_admin(request)
    safe_limit = max(1, min(int(limit or 200), 2000))
    rows = list(devices_collection.find().sort("last_seen", -1).limit(safe_limit))
    result = []
    for r in rows:
        if r and "_id" in r:
            r["_id"] = str(r["_id"])
        result.append(r)
    return result
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import APIRouter, Request, Body, HTTPException
from pydantic import BaseModel, Field

from ..base import devices_collection
from .main_auth import extract_bearer_token, _get_user_from_token, require_admin


devices_router = APIRouter()


class DeviceRegisterRequest(BaseModel):
    device_id: Optional[str] = Field(default=None, max_length=200)
    ip: Optional[str] = Field(default=None, max_length=64)
    hostname: Optional[str] = Field(default="", max_length=200)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


@devices_router.post("/devices/register")
def register_device(request: Request, data: DeviceRegisterRequest = Body(...)):
    """Register or update a device (phone) IP. Optional bearer token associates the device with a user."""
    token = extract_bearer_token(request)
    user_id = None
    user_email = ""
    if token:
        try:
            user = _get_user_from_token(token)
            user_id = str(user.id)
            user_email = getattr(user, "email", "") or ""
        except HTTPException:
            # Token invalid -> ignore and allow anonymous registration
            user_id = None
        except Exception:
            user_id = None

    ip = (data.ip or (request.client.host if getattr(request, "client", None) else None) or "").strip()
    device_id = str(data.device_id).strip() if data.device_id else None
    hostname = str(data.hostname or "").strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not device_id and not ip:
        raise HTTPException(status_code=400, detail="device_id ou ip requis")

    query = {"device_id": device_id} if device_id else {"ip": ip}

    update_doc = {
        "$set": {
            "device_id": device_id,
            "ip": ip,
            "hostname": hostname,
            "user_id": user_id,
            "email": user_email,
            "metadata": data.metadata or {},
            "last_seen": now_iso,
        },
        "$setOnInsert": {"created_at": now_iso},
    }

    try:
        devices_collection.update_one(query, update_doc, upsert=True)
        doc = devices_collection.find_one(query)
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return {"success": True, "device": doc}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur enregistrement: {e}")


@devices_router.get("/admin/devices")
def list_devices(request: Request, limit: int = 200):
    """Admin: list registered devices."""
    require_admin(request)
    safe_limit = max(1, min(int(limit or 200), 2000))
    rows = list(devices_collection.find().sort("last_seen", -1).limit(safe_limit))
    result = []
    for r in rows:
        if r and "_id" in r:
            r["_id"] = str(r["_id"])
        result.append(r)
    return result
