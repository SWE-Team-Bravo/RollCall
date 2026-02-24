import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import get_collection

USERS_JSON = Path(__file__).parent.parent / "auth" / "users.json"


def main():
    collection = get_collection("users")
    if collection is None:
        print("ERROR: Could not connect to MongoDB. Check MONGODB_URI in .env.")
        sys.exit(1)
    assert collection is not None

    data = json.loads(USERS_JSON.read_text())

    inserted = 0
    skipped = 0
    for email, info in data["usernames"].items():
        if collection.find_one({"email": email}):
            print(f"  skip   {email} (already exists)")
            skipped += 1
            continue

        collection.insert_one({
            "first_name": info["first_name"],
            "last_name": info["last_name"],
            "email": email,
            "password_hash": info["password_hash"],
            "roles": info["roles"],
        })
        print(f"  insert {email} ({', '.join(info['roles'])})")
        inserted += 1

    print(f"\nDone: {inserted} inserted, {skipped} skipped.")


if __name__ == "__main__":
    main()
