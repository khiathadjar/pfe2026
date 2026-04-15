import os
import sys
from threading import Thread
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

if __package__ is None:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from backend.base import keyword_index_collection, things_collection
from backend.routers.main_auth import auth_router
from backend.routers.main_localisation import localisation_router
from backend.routers.main_borrow import borrow_router
from backend.routers.main_crud import crud_router
from backend.routers.main_notifications import notifications_router
from backend.routers.main_recherche import recherche_router
from backend.routers.main_devices import devices_router

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "bdd.env"))

index_mot_cle_collection = keyword_index_collection

app = FastAPI()

def _cleanup_orphan_keywords_on_startup():
    """Nettoie automatiquement les mots-clés orphelins au démarrage."""
    try:
        all_keyword_thing_ids = list(keyword_index_collection.distinct("thingId"))
        orphan_thing_ids = []
        
        for thing_id in all_keyword_thing_ids:
            thing_id_clean = str(thing_id).strip()
            if not things_collection.find_one({"id": thing_id_clean}):
                orphan_thing_ids.append(thing_id_clean)
        
        if orphan_thing_ids:
            result = keyword_index_collection.delete_many({"thingId": {"$in": orphan_thing_ids}})
            print(f"🧹 Nettoyage au démarrage: {result.deleted_count} mots-clés supprimés")
    except Exception as e:
        print(f"⚠️  Erreur nettoyage: {e}")


def _initialize_view_counts_on_startup():
    """Initialise les compteurs de vues (view_count) pour tous les objets."""
    try:
        result = things_collection.update_many(
            {"view_count": {"$exists": False}},
            {"$set": {"view_count": 0}}
        )
        if result.modified_count > 0:
            print(f"📊 Initialisation view_count: {result.modified_count} objets mis à jour")
    except Exception as e:
        print(f"⚠️  Erreur initialisation view_count: {e}")


def _background_cleanup_task():
    """Tâche de fond qui nettoie les mots-clés orphelins toutes les 5 minutes."""
    while True:
        try:
            time.sleep(300)
            
            all_keyword_thing_ids = list(keyword_index_collection.distinct("thingId"))
            orphan_thing_ids = []
            
            for thing_id in all_keyword_thing_ids:
                thing_id_clean = str(thing_id).strip()
                if not things_collection.find_one({"id": thing_id_clean}):
                    orphan_thing_ids.append(thing_id_clean)
            
            if orphan_thing_ids:
                result = keyword_index_collection.delete_many({"thingId": {"$in": orphan_thing_ids}})
                print(f"🧹 Nettoyage ({result.deleted_count} keywords)")
        except Exception as e:
            print(f"⚠️  Erreur nettoyage: {e}")


def _get_origins() -> list[str]:
    configured = os.getenv(
        "FRONTEND_ORIGINS",
        "http://127.0.0.1:5501,http://localhost:5501,http://127.0.0.1:5500,http://localhost:5500",
    )
    return [origin.strip() for origin in configured.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Nettoyage automatique au démarrage
_cleanup_orphan_keywords_on_startup()
_initialize_view_counts_on_startup()

# Démarrer la tâche de fond pour le nettoyage périodique
cleanup_thread = Thread(target=_background_cleanup_task, daemon=True)
cleanup_thread.start()

app.include_router(localisation_router)
app.include_router(recherche_router)
app.include_router(auth_router)
app.include_router(borrow_router)
app.include_router(crud_router)
app.include_router(notifications_router)
app.include_router(devices_router)

@app.get("/")
def root():
    return {"message": "API is running"}



