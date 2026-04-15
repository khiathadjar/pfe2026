import os
from dotenv import load_dotenv
from supabase import create_client

# Charger les variables du fichier bdd.env
load_dotenv("bdd.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Client principal (utilise la key normale définie dans bdd.env)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Client admin/service (optionnel) — DOIT utiliser la Service Role Key pour pouvoir
# appeler les endpoints admin (delete_user, etc.). Ajoutez SUPABASE_SERVICE_ROLE dans bdd.env.
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE") or os.getenv("SUPABASE_SERVICE_KEY")
if SUPABASE_SERVICE_ROLE:
    try:
        supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE)
    except Exception:
        supabase_admin = supabase
else:
    supabase_admin = supabase


def signup_user(email, password):
    return supabase.auth.sign_up({"email": email, "password": password})


def login_user(email, password):
    return supabase.auth.sign_in_with_password({"email": email, "password": password})


def reset_password_email(email, redirect_to=None):
    options = {"redirect_to": redirect_to} if redirect_to else None
    return supabase.auth.reset_password_for_email(email, options)


def delete_user_admin(user_id: str) -> tuple[bool, str | None]:
    """Try to delete a Supabase auth user using the admin client.

    Returns (success, error_message).
    Note: this requires a Service Role key configured as SUPABASE_SERVICE_ROLE in bdd.env.
    """
    try:
        client = supabase_admin
        admin_api = getattr(client.auth, "admin", None) or getattr(client.auth, "api", None)
        if admin_api and hasattr(admin_api, "delete_user"):
            # Some implementations accept (user_id) or (user_id, should_soft_delete)
            try:
                admin_api.delete_user(user_id)
            except TypeError:
                # fallback if API expects two args
                admin_api.delete_user(user_id, False)
            return True, None
        else:
            return False, "Admin API unavailable (missing service role key)"
    except Exception as e:
        return False, str(e)