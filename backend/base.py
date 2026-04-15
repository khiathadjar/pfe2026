from pymongo import MongoClient
from pymongo.errors import ConfigurationError, PyMongoError
from dotenv import load_dotenv
import os

# Charger les variables du fichier bdd.env
load_dotenv("bdd.env")

MONGO_URI = os.getenv("MONGO_URI")


class _NullResult:
    acknowledged = False
    inserted_id = None
    modified_count = 0
    deleted_count = 0
    upserted_id = None


class _NullCursor:
    def sort(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def __iter__(self):
        return iter(())


class _NullCollection:
    def find(self, *args, **kwargs):
        return _NullCursor()

    def find_one(self, *args, **kwargs):
        return None

    def find_one_and_update(self, *args, **kwargs):
        return None

    def insert_one(self, *args, **kwargs):
        return _NullResult()

    def insert_many(self, *args, **kwargs):
        return _NullResult()

    def update_one(self, *args, **kwargs):
        return _NullResult()

    def update_many(self, *args, **kwargs):
        return _NullResult()

    def delete_one(self, *args, **kwargs):
        return _NullResult()

    def delete_many(self, *args, **kwargs):
        return _NullResult()

    def count_documents(self, *args, **kwargs):
        return 0

    def aggregate(self, *args, **kwargs):
        return _NullCursor()


class _NullDatabase:
    def __init__(self):
        self.things = _NullCollection()
        self.keyword_index = _NullCollection()
        self.notifications = _NullCollection()
        self.user_history = _NullCollection()
        self.devices = _NullCollection()

    def __getattr__(self, name):
        collection = _NullCollection()
        setattr(self, name, collection)
        return collection


class _NullAdmin:
    def command(self, *args, **kwargs):
        return {"ok": 1}


class _NullClient:
    def __init__(self):
        self.admin = _NullAdmin()
        self._database = _NullDatabase()

    def __getattr__(self, name):
        return self._database


def _build_client():
    try:
        real_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        real_client.admin.command("ping")
        print("MongoDB: connected")
        return real_client
    except (ConfigurationError, PyMongoError, Exception) as exc:
        print(f"MongoDB: not connected ({exc})")
        return _NullClient()


client = _build_client()

db = client.smart_building
things_collection = db.things
# Collection officielle des mots-cles pour la recherche
keyword_index_collection = db.keyword_index
notifications_collection = db.notifications

# Aliases de compatibilite pour l'ancien code
keyword_index_collection = keyword_index_collection
keyword_index_collection = keyword_index_collection
user_history_collection = db.user_history
devices_collection = db.devices
