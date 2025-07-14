import redis
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from ..config import get_settings

settings = get_settings()

class SessionManager:
    """Simple Redis-based session manager."""

    def __init__(self) -> None:
        self.redis = redis.from_url(settings.REDIS_URL)
        self.expire = timedelta(hours=24)

    def create(self, user_id: str) -> str:
        session_id = f"sess:{user_id}:{datetime.utcnow().timestamp()}"
        data = {"user_id": user_id, "created_at": datetime.utcnow().isoformat()}
        self.redis.setex(session_id, self.expire, json.dumps(data))
        return session_id

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        val = self.redis.get(session_id)
        if val:
            return json.loads(val)
        return None
