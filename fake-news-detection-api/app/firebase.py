import os
import firebase_admin
from firebase_admin import credentials, firestore

SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_CRED_PATH")
if not SERVICE_ACCOUNT_PATH:
    raise RuntimeError("Missing FIREBASE_CRED_PATH environment variable")

cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()
