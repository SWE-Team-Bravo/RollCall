from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from config.settings import MONGODB_URI, MONGODB_DB

__client = None


def get_client() -> MongoClient | None:
    global __client

    if not MONGODB_URI:
        return None

    if __client is None:
        __client = MongoClient(MONGODB_URI)
        _ensure_indexes()

    return __client


def get_db() -> Database | None:
    client = get_client()
    if client is None:
        return None
    return client[MONGODB_DB]


def get_collection(collection_name: str) -> Collection | None:
    db = get_db()
    if db is None:
        return None
    return db[collection_name]


def _ensure_indexes() -> None:
    from utils.create_indexes import create_indexes
    create_indexes()
