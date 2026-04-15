from datetime import datetime, timezone
import sys
from typing import Any

from backend.base import notifications_collection


def _main_module():
    return sys.modules.get("main")


def _notifications_collection():
    module = _main_module()
    return getattr(module, "notifications_collection", notifications_collection) if module else notifications_collection


def create_notification(
    target_role: str,
    title: str,
    message: str,
    notif_type: str = "info",
    recipient_user_id: str = "",
    recipient_email: str = "",
    actor_user_id: str = "",
    actor_email: str = "",
    metadata: dict[str, Any] | None = None,
) -> str | None:
    try:
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "target_role": str(target_role or "user").strip().lower(),
            "recipient_user_id": str(recipient_user_id or "").strip(),
            "recipient_email": str(recipient_email or "").strip(),
            "title": str(title or "Notification").strip(),
            "message": str(message or "").strip(),
            "type": str(notif_type or "info").strip().lower(),
            "is_read": False,
            "actor_user_id": str(actor_user_id or "").strip(),
            "actor_email": str(actor_email or "").strip(),
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        inserted = _notifications_collection().insert_one(doc)

        return str(inserted.inserted_id)
    except Exception as e:
        print(f"Erreur create_notification: {e}")
        return None
