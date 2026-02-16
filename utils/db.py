from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.results import InsertOneResult
from config.settings import MONGODB_URI, MONGODB_DB

__client = None


def get_client() -> MongoClient | None:
    global __client

    if not MONGODB_URI:
        return None

    if __client is None:
        __client = MongoClient(MONGODB_URI)

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


def insert_one(collection_name: str, document: dict) -> InsertOneResult | None:
    collection = get_collection(collection_name)
    if collection is None:
        return None
    return collection.insert_one(document)


def find_one(collection_name: str, query: dict) -> dict | None:
    collection = get_collection(collection_name)
    if collection is None:
        return None
    return collection.find_one(query)
