from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import os
import httpx

from ..base import user_history_collection, notifications_collection

from ..supabase_client import reset_password_email, signup_user, supabase, delete_user_admin
from ..notifications_service import create_notification


auth_router = APIRouter()

HISTORY_RETENTION_DAYS = 45
HISTORY_MAX_ENTRIES_PER_USER = 120
HISTORY_PRUNE_SCAN_BUFFER = 5000


def _get_frontend_base_url() -> str:
    configured = os.getenv(
        "FRONTEND_ORIGINS",
        "http://127.0.0.1:5501,http://localhost:5501,http://127.0.0.1:5500,http://localhost:5500",
    )
    origins = [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    for origin in origins:
        if not origin.startswith(("http://127.0.0.1", "https://127.0.0.1", "http://localhost", "https://localhost")):
            return origin
    return origins[0] if origins else "http://127.0.0.1:5501"


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=6, max_length=128)


class SignupRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=6, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)


class UserHistoryRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=120)
    detail: str = Field(default="", max_length=500)
    status: str = Field(default="Succes", max_length=80)


class UpdateUserRoleRequest(BaseModel):
    role: str = Field(..., min_length=4, max_length=10)


def extract_bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header.replace("Bearer ", "", 1).strip() or None


def _get_user_from_token(token: str):
    """Resolve a Supabase user from JWT with resilient upstream error handling."""
    last_http_error: Exception | None = None
    for _ in range(2):
        try:
            user_response = supabase.auth.get_user(token)
            user = getattr(user_response, "user", None)
            if not user:
                raise HTTPException(status_code=401, detail="Token invalide")
            return user
        except HTTPException:
            raise
        except httpx.HTTPError as e:
            # Supabase transient network/protocol error (seen as RemoteProtocolError).
            last_http_error = e
            continue
        except Exception as e:
            message = str(e).lower()
            if "jwt" in message or "token" in message or "unauthorized" in message:
                raise HTTPException(status_code=401, detail="Token invalide")
            raise HTTPException(status_code=503, detail="Service auth temporairement indisponible")

    print(f"Erreur Supabase get_user: {last_http_error}")
    raise HTTPException(status_code=503, detail="Service auth temporairement indisponible")


def get_role_from_token(token: str) -> str:
    user = _get_user_from_token(token)
    profile = supabase.table("utilisateur").select("role").eq("id", user.id).maybe_single().execute()
    return profile.data.get("role", "user") if profile.data else "user"


def require_admin(request: Request) -> None:
    token = extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Token manquant")
    if get_role_from_token(token) != "admin":
        raise HTTPException(status_code=403, detail="Acces refuse: Admin requis")


def _get_authenticated_user(request: Request):
    token = extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Token manquant")
    return _get_user_from_token(token)


def _get_user_profile_row(user_id: str) -> dict:
    try:
        query = supabase.table("utilisateur").select("*").eq("id", user_id).maybe_single().execute()
        if query and isinstance(query.data, dict):
            return query.data
    except Exception as e:
        print(f"Erreur lecture profil utilisateur: {e}")
    return {}


def _display_name_from_profile(email: str, profile_row: dict | None = None) -> str:
    profile_row = profile_row or {}
    for key in ("display_name", "full_name", "name", "nom"):
        value = str(profile_row.get(key, "") or "").strip()
        if value:
            return value

    local_part = str(email or "").split("@", 1)[0].strip()
    if not local_part:
        return "Utilisateur"

    local_part = local_part.replace(".", " ").replace("_", " ").replace("-", " ")
    return " ".join(piece.capitalize() for piece in local_part.split() if piece)


def _history_retention_cutoff_iso() -> str:
    cutoff = datetime.now(timezone.utc).timestamp() - (HISTORY_RETENTION_DAYS * 24 * 60 * 60)
    return datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()


def _prune_user_history(user_id: str | None = None) -> None:
    try:
        # Keep the collection from growing indefinitely by trimming old rows globally.
        user_history_collection.delete_many({"created_at": {"$lt": _history_retention_cutoff_iso()}})

        if user_id:
            rows = list(
                user_history_collection.find({"user_id": str(user_id)}, {"_id": 1})
                .sort("created_at", -1)
                .limit(HISTORY_MAX_ENTRIES_PER_USER + HISTORY_PRUNE_SCAN_BUFFER)
            )
            if len(rows) > HISTORY_MAX_ENTRIES_PER_USER:
                stale_ids = [row.get("_id") for row in rows[HISTORY_MAX_ENTRIES_PER_USER:] if row.get("_id")]
                if stale_ids:
                    user_history_collection.delete_many({"_id": {"$in": stale_ids}})
    except Exception as e:
        print(f"Erreur purge historique: {e}")


def _format_history_date(raw_date: str, raw_created_at: str) -> str:
    date_value = str(raw_date or "").strip()
    if date_value:
        return date_value

    created_value = str(raw_created_at or "").strip()
    if not created_value:
        return "-"

    try:
        parsed = datetime.fromisoformat(created_value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return created_value


@auth_router.post("/login")
def login(data: LoginRequest = Body(...)):
    email = data.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Email invalide")

    try:
        auth_res = supabase.auth.sign_in_with_password({"email": email, "password": data.password})
        if not auth_res.user or not auth_res.session:
            raise HTTPException(status_code=401, detail="Identifiants invalides")

        user_role = "user"
        display_name = _display_name_from_profile(email)
        try:
            query = supabase.table("utilisateur").select("*").eq("id", auth_res.user.id).maybe_single().execute()
            if query.data:
                user_role = query.data.get("role", "user")
                display_name = _display_name_from_profile(email, query.data)
        except Exception as e:
            print(f"Erreur lecture role: {e}")

        create_notification(
            target_role="user",
            recipient_user_id=str(auth_res.user.id),
            recipient_email=email,
            actor_user_id=str(auth_res.user.id),
            actor_email=email,
            title="Connexion reussie",
            message="Connexion reussie a votre espace IntelliBuild.",
            notif_type="success",
            metadata={"action": "login"},
        )

        return {
            "access_token": auth_res.session.access_token,
            "user_id": str(auth_res.user.id),
            "role": user_role,
            "email": email,
            "display_name": display_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erreur login: {e}")
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")


@auth_router.post("/signup")
def signup(data: SignupRequest = Body(...)):
    email = data.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Email invalide")

    try:
        res = signup_user(email, data.password)
        if res.user:
            supabase.table("utilisateur").insert({
                "id": res.user.id,
                "email": email,
                "role": "user",
            }).execute()
            return {"success": True, "message": "Compte cree"}

        raise HTTPException(status_code=400, detail="Erreur signup")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erreur signup: {e}")
        raise HTTPException(status_code=500, detail="Impossible de creer le compte")


@auth_router.post("/auth/forgot")
def forgot_password(data: ForgotPasswordRequest = Body(...)):
    try:
        email = data.email.strip().lower()
        reset_password_email(email, f"{_get_frontend_base_url()}/reset.html")

        recipient_user_id = ""
        try:
            user_row = supabase.table("utilisateur").select("id").eq("email", email).maybe_single().execute()
            if user_row and user_row.data and user_row.data.get("id"):
                recipient_user_id = str(user_row.data.get("id"))
        except Exception as e:
            print(f"Erreur lookup user forgot: {e}")

        create_notification(
            target_role="user",
            recipient_user_id=recipient_user_id,
            recipient_email=email,
            actor_email=email,
            title="Reinitialisation mot de passe demandee",
            message="Une demande de reinitialisation de mot de passe a ete enregistree.",
            notif_type="info",
            metadata={"action": "forgot_password"},
        )

        return {"success": True}
    except Exception as e:
        print(f"Erreur forgot: {e}")
        raise HTTPException(status_code=500, detail="Erreur email")


@auth_router.get("/user/profile")
def get_user_profile(request: Request):
    user = _get_authenticated_user(request)
    profile_row = _get_user_profile_row(str(user.id))
    email = getattr(user, "email", "") or profile_row.get("email", "") or ""
    role = str(profile_row.get("role", "user") or "user")
    return {
        "id": str(user.id),
        "email": email,
        "role": role,
        "display_name": _display_name_from_profile(email, profile_row),
    }


@auth_router.get("/user/history")
def get_user_history(request: Request):
    user = _get_authenticated_user(request)
    _prune_user_history(str(user.id))
    rows = list(user_history_collection.find({"user_id": str(user.id)}).sort("created_at", -1).limit(HISTORY_MAX_ENTRIES_PER_USER))
    result = []
    for row in rows:
        row["_id"] = str(row.get("_id"))
        result.append(row)
    return result


@auth_router.post("/user/history")
def add_user_history(request: Request, data: UserHistoryRequest = Body(...)):
    user = _get_authenticated_user(request)
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": str(user.id),
        "email": getattr(user, "email", "") or "",
        "action": data.action,
        "detail": data.detail,
        "status": data.status,
        "date": now.strftime("%d/%m/%Y %H:%M:%S"),
        "created_at": now.isoformat(),
    }
    inserted = user_history_collection.insert_one(doc)
    _prune_user_history(str(user.id))
    return {"success": True, "id": str(inserted.inserted_id)}


@auth_router.get("/admin/users")
def get_admin_users(request: Request):
    require_admin(request)
    rows = supabase.table("utilisateur").select("id,email,role").execute()
    data = rows.data if rows and isinstance(rows.data, list) else []
    return [
        {
            "id": str(item.get("id", "")),
            "email": str(item.get("email", "") or ""),
            "role": str(item.get("role", "user") or "user"),
            "display_name": _display_name_from_profile(str(item.get("email", "") or ""), item),
        }
        for item in data
        if item.get("id")
    ]


@auth_router.get("/admin/user-activity")
def get_admin_user_activity(request: Request, limit: int = 200):
    require_admin(request)

    _prune_user_history()

    safe_limit = max(20, min(int(limit or 200), 500))

    # Focus admin supervision on object lifecycle and key user activity.
    rows = list(
        user_history_collection.find(
            {
                "action": {
                    "$in": [
                        "EMPRUNT_DEBUT",
                        "EMPRUNT_FIN",
                        "Session",
                    ]
                }
            }
        )
        .sort("created_at", -1)
        .limit(safe_limit)
    )

    result = []
    for row in rows:
        action = str(row.get("action", "") or "")
        detail = str(row.get("detail", "") or "")
        user_id = str(row.get("user_id", "") or "")
        email = str(row.get("email", "") or "")
        created_at = str(row.get("created_at", "") or "")
        date_value = _format_history_date(str(row.get("date", "") or ""), created_at)

        # Skip explicit admin-labelled logs to keep this table user-centric.
        if action.lower().startswith("admin -"):
            continue

        # Remove low-value consultation spam from admin activity table.
        detail_lower = detail.lower()
        if action.lower() == "objet" and "consultation" in detail_lower:
            continue

        result.append(
            {
                "_id": str(row.get("_id")),
                "user_id": user_id,
                "email": email or (f"user:{user_id[:8]}" if user_id else "-"),
                "action": action,
                "detail": detail,
                "status": str(row.get("status", "") or ""),
                "thing_id": str(row.get("thing_id", "") or ""),
                "thing_name": str(row.get("thing_name", "") or ""),
                "date": date_value,
                "created_at": created_at,
            }
        )

    return result


@auth_router.patch("/admin/users/{target_user_id}/role")
def update_admin_user_role(target_user_id: str, request: Request, data: UpdateUserRoleRequest = Body(...)):
    require_admin(request)
    actor = _get_authenticated_user(request)
    role = str(data.role or "").strip().lower()
    if role not in {"admin", "user"}:
        raise HTTPException(status_code=400, detail="Role invalide")

    row = _get_user_profile_row(target_user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    supabase.table("utilisateur").update({"role": role}).eq("id", target_user_id).execute()

    recipient_email = str(row.get("email", "") or "")
    create_notification(
        target_role=role,
        recipient_user_id=target_user_id,
        recipient_email=recipient_email,
        actor_user_id=str(actor.id),
        actor_email=str(getattr(actor, "email", "") or ""),
        title="Role mis a jour",
        message=f"Votre role a ete modifie vers '{role}'.",
        notif_type="info",
        metadata={"action": "role_update", "new_role": role},
    )

    return {
        "success": True,
        "id": target_user_id,
        "role": role,
        "email": recipient_email,
        "display_name": _display_name_from_profile(recipient_email, row),
    }


@auth_router.delete("/admin/users/{target_user_id}")
def delete_admin_user(target_user_id: str, request: Request):
    require_admin(request)
    actor = _get_authenticated_user(request)

    row = _get_user_profile_row(target_user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    recipient_email = str(row.get("email", "") or "")

    # Try to remove the auth account from Supabase (best-effort).
    auth_deleted = False
    auth_error = None
    try:
        ok, err = delete_user_admin(target_user_id)
        auth_deleted = bool(ok)
        auth_error = err
        if not ok:
            print(f"delete_user_admin returned error: {err}")
    except Exception as e:
        auth_error = str(e)
        print(f"Erreur suppression auth supabase: {e}")

    # Remove profile row from utilisateur table
    try:
        supabase.table("utilisateur").delete().eq("id", target_user_id).execute()
    except Exception as e:
        print(f"Erreur suppression ligne utilisateur: {e}")

    # Remove related MongoDB documents (history, notifications)
    try:
        user_history_collection.delete_many({"user_id": target_user_id})
    except Exception as e:
        print(f"Erreur suppression historique utilisateur: {e}")
    try:
        notifications_collection.delete_many({"$or": [{"recipient_user_id": target_user_id}, {"actor_user_id": target_user_id}]})
    except Exception as e:
        print(f"Erreur suppression notifications utilisateur: {e}")

    result = {"success": True, "id": target_user_id, "email": recipient_email}
    result["auth_deleted"] = auth_deleted
    if auth_error:
        result["auth_error"] = str(auth_error)
    return result
