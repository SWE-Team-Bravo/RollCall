import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = "RollCall"
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "rollcall_db")
AUTH_COOKIE_KEY = os.getenv("AUTH_COOKIE_KEY")
