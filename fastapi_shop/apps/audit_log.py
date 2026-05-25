from datetime import datetime, timezone
from db import db
from constants import COLLECTION_AUDIT_LOG

audit_collection = db[COLLECTION_AUDIT_LOG]


async def log_admin_action(admin_user: str, action: str, entity_type: str, entity_id: str, summary: str):
    doc = {
        "admin_user": admin_user,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "summary": summary,
        "created": datetime.now(timezone.utc),
    }
    await audit_collection.insert_one(doc)
