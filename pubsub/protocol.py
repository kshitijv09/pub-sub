"""Protocol message shapes for HTTP and WebSocket (health, subscribe, etc.)."""

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


# ---- Health ----

@dataclass
class HealthResponse:
    """Response for GET /health."""
    uptime_sec: float
    topics: int
    subscribers: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uptime_sec": int(self.uptime_sec),
            "topics": self.topics,
            "subscribers": self.subscribers,
        }


# ---- Subscribe ----

@dataclass
class SubscribeRequest:
    """Client request to subscribe to a topic."""
    topic: str
    subscriber_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubscribeRequest":
        return cls(
            topic=str(data["topic"]),
            subscriber_id=data.get("subscriber_id"),
        )


@dataclass
class SubscribeResponse:
    """Server response after subscribe. replay is list of event dicts when last_n > 0."""
    ok: bool
    topic: str
    subscriber_id: Optional[str] = None
    error: Optional[str] = None
    replay: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d.get("replay") is None:
            d.pop("replay", None)
        return d


# ---- Topics ----

@dataclass
class TopicCreatedResponse:
    """Response for POST /topics (201 Created)."""
    status: str = "created"
    topic: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TopicDeletedResponse:
    """Response for DELETE /topics/{name} (200 OK)."""
    status: str = "deleted"
    topic: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def topics_list_response(topics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Response for GET /topics."""
    return {"topics": topics}


def stats_response(topics_stats: Dict[str, Dict[str, int]]) -> Dict[str, Any]:
    """Response for GET /stats."""
    return {"topics": topics_stats}


# ---- WebSocket: Server → Client ----

# Error codes (use with ws_error)
ERROR_BAD_REQUEST = "BAD_REQUEST"
ERROR_TOPIC_NOT_FOUND = "TOPIC_NOT_FOUND"
ERROR_SLOW_CONSUMER = "SLOW_CONSUMER"
ERROR_UNAUTHORIZED = "UNAUTHORIZED"
ERROR_INTERNAL = "INTERNAL"


def ws_ts() -> str:
    """Current UTC timestamp in ISO 8601 (e.g. 2025-08-25T10:00:00Z)."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ws_ack(request_id: Optional[str], topic: Optional[str], ts: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"type": "ack", "status": "ok", "ts": ts}
    if request_id is not None:
        out["request_id"] = request_id
    if topic is not None:
        out["topic"] = topic
    return out


def ws_event(topic: str, message: Dict[str, Any], ts: str) -> Dict[str, Any]:
    return {"type": "event", "topic": topic, "message": message, "ts": ts}


def ws_error(request_id: Optional[str], code: str, message: str, ts: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "type": "error",
        "error": {"code": code, "message": message},
        "ts": ts,
    }
    if request_id is not None:
        out["request_id"] = request_id
    return out


def ws_pong(request_id: str, ts: str) -> Dict[str, Any]:
    return {"type": "pong", "request_id": request_id, "ts": ts}


def ws_info(msg: str, ts: str, topic: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"type": "info", "msg": msg, "ts": ts}
    if topic is not None:
        out["topic"] = topic
    return out
