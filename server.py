"""HTTP server: health, topics, subscribe, stats. WebSocket: ping, subscribe, unsubscribe, publish."""

from dotenv import load_dotenv
load_dotenv()

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from pubsub.message import Message
from pubsub.protocol import (
    HealthResponse,
    SubscribeRequest,
    SubscribeResponse,
    TopicCreatedResponse,
    TopicDeletedResponse,
    topics_list_response,
    stats_response,
    ws_ack,
    ws_error,
    ws_event,
    ws_info,
    ws_pong,
    ws_ts,
    ERROR_BAD_REQUEST,
    ERROR_TOPIC_NOT_FOUND,
    ERROR_SLOW_CONSUMER,
    ERROR_UNAUTHORIZED,
    ERROR_INTERNAL,
)
from pubsub.registry import Registry

registry = Registry()
_start_time: float = 0.0

# Active WebSocket connections for server-initiated heartbeat
_ws_connections: set = set()
_heartbeat_task: asyncio.Task | None = None

# X-API-Key is compulsory: API_KEY must be set in env (or .env)
def _get_expected_api_key() -> str | None:
    return (os.environ.get("API_KEY") or "").strip() or None


class XAPIKeyMiddleware(BaseHTTPMiddleware):
    """Require X-API-Key header; API_KEY env must be set."""
    async def dispatch(self, request: Request, call_next):
        if request.scope.get("type") == "websocket":
            return await call_next(request)
        expected = _get_expected_api_key()
        if not expected:
            return JSONResponse(
                status_code=503,
                content={"error": "UNAUTHORIZED", "message": "X-API-Key required (API_KEY env not set)"},
            )
        key = (request.headers.get("X-API-Key") or request.headers.get("x-api-key") or "").strip()
        if key != expected:
            return JSONResponse(
                status_code=401,
                content={"error": "UNAUTHORIZED", "message": "invalid or missing X-API-Key"},
            )
        return await call_next(request)


async def _heartbeat_loop() -> None:
    """Periodically send info heartbeat (msg: ping) to all connected WebSocket clients."""
    interval = float(os.environ.get("HEARTBEAT_INTERVAL_SEC", "30"))
    if interval <= 0:
        return
    while True:
        await asyncio.sleep(interval)
        payload = ws_info("ping", ws_ts())
        dead = []
        for ws in _ws_connections:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _ws_connections.discard(ws)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _start_time, _heartbeat_task
    _start_time = time.time()
    _heartbeat_task = asyncio.create_task(_heartbeat_loop())
    yield
    if _heartbeat_task is not None:
        _heartbeat_task.cancel()
        try:
            await _heartbeat_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Pub-Sub API", lifespan=lifespan)
app.add_middleware(XAPIKeyMiddleware)

router = APIRouter(prefix="/api/v1")
app.include_router(router)


# ---- Health ----

@router.get("/health")
def health() -> JSONResponse:
    """GET /health → { uptime_sec, topics, subscribers }."""
    uptime = time.time() - _start_time
    body = HealthResponse(
        uptime_sec=uptime,
        topics=registry.topic_count(),
        subscribers=registry.total_subscriber_count(),
    ).to_dict()
    return JSONResponse(content=body, status_code=200)


# ---- Stats ----

@router.get("/stats")
def stats() -> JSONResponse:
    """GET /stats → { topics: { name: { messages, subscribers } } }."""
    body = stats_response(registry.topic_stats())
    return JSONResponse(content=body, status_code=200)


# ---- Topics ----

class TopicCreateBody(BaseModel):
    name: str


@router.post("/topics")
def create_topic(body: TopicCreateBody) -> JSONResponse:
    """POST /topics { name } → 201 { status: created, topic } or 409 Conflict."""
    name = (body.name or "").strip()
    if not name:
        return JSONResponse(
            content={"error": "name is required"},
            status_code=400,
        )
    topic, created = registry.create_topic(name)
    if not created:
        return JSONResponse(
            content={"error": "topic already exists", "topic": name},
            status_code=409,
        )
    return JSONResponse(
        content=TopicCreatedResponse(status="created", topic=name).to_dict(),
        status_code=201,
    )


@router.delete("/topics/{name}")
def delete_topic(name: str) -> JSONResponse:
    """DELETE /topics/{name} → 200 { status: deleted, topic } or 404."""
    if not name:
        return JSONResponse(content={"error": "name is required"}, status_code=400)
    deleted = registry.delete_topic(name)
    if not deleted:
        return JSONResponse(
            content={"error": "topic not found", "topic": name},
            status_code=404,
        )
    return JSONResponse(
        content=TopicDeletedResponse(status="deleted", topic=name).to_dict(),
        status_code=200,
    )


@router.get("/topics")
def list_topics() -> JSONResponse:
    """GET /topics → { topics: [ { name, subscribers } ] }."""
    body = topics_list_response(registry.list_topics())
    return JSONResponse(content=body, status_code=200)


# ---- Subscribe ----

class SubscribeBody(BaseModel):
    topic: str
    subscriber_id: str | None = None
    last_n: int = 0


@router.post("/subscribe")
def subscribe(body: SubscribeBody) -> JSONResponse:
    """Subscribe to a topic (topic must exist). If last_n > 0, response includes replay of last_n messages."""
    req = SubscribeRequest(topic=body.topic, subscriber_id=body.subscriber_id)
    if not req.topic.strip():
        return JSONResponse(
            content=SubscribeResponse(ok=False, topic=req.topic, error="topic is required").to_dict(),
            status_code=400,
        )
    topic = registry.get_topic(req.topic)
    if topic is None:
        return JSONResponse(
            content=SubscribeResponse(ok=False, topic=req.topic, error="topic not found").to_dict(),
            status_code=404,
        )
    subscriber = registry.subscribe_to_topic(req.topic, req.subscriber_id)
    replay: list | None = None
    if body.last_n and body.last_n > 0:
        replay = []
        for message, t in topic.get_last_n(body.last_n):
            replay.append(ws_event(t.name, {"id": message.message_id, "payload": message.payload}, ws_ts()))
    resp = SubscribeResponse(ok=True, topic=req.topic, subscriber_id=subscriber.subscriber_id, replay=replay)
    return JSONResponse(content=resp.to_dict(), status_code=200)


# ---- WebSocket (ping, subscribe, unsubscribe, publish) ----

async def _ws_send(websocket: WebSocket, payload: dict) -> None:
    """Send JSON to client; on failure sends SLOW_CONSUMER error if possible."""
    try:
        await websocket.send_json(payload)
    except Exception:
        try:
            await websocket.send_json(ws_error(
                None, ERROR_SLOW_CONSUMER,
                "delivery failed or subscriber queue overflow",
                ws_ts(),
            ))
        except Exception:
            pass


def _make_send_callback(websocket: WebSocket):
    """Callback that schedules sending a dict over the websocket."""
    def send_cb(d: dict) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_ws_send(websocket, d))
        except RuntimeError:
            pass
    return send_cb


def _ws_api_key_ok(websocket: WebSocket) -> bool:
    """Return True if X-API-Key matches API_KEY env. API_KEY must be set."""
    expected = _get_expected_api_key()
    if not expected:
        return False
    raw = websocket.scope.get("headers") or []
    key = ""
    for k, v in raw:
        name = k.decode("utf-8", errors="ignore").lower()
        if name == "x-api-key":
            key = v.decode("utf-8", errors="ignore").strip()
            break
    return key == expected


@router.websocket("/ws")
async def websocket_handler(websocket: WebSocket) -> None:
    """
    WebSocket endpoint. Messages: ping, subscribe, unsubscribe, publish.
    Server replies: pong, ack, event, error, info.
    """
    await websocket.accept()
    if not _ws_api_key_ok(websocket):
        await websocket.send_json(ws_error(
            None, ERROR_UNAUTHORIZED,
            "invalid or missing X-API-Key",
            ws_ts(),
        ))
        await websocket.close()
        return
    _ws_connections.add(websocket)
    ts = ws_ts()
    send_cb = _make_send_callback(websocket)
    current_connection_subscribers: set = set()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json(ws_error(None, ERROR_BAD_REQUEST, "Invalid JSON", ts))
                continue
            msg_type = msg.get("type")
            request_id = msg.get("request_id")

            if msg_type == "ping":
                await websocket.send_json(ws_pong(msg.get("request_id", ""), ws_ts()))
                continue

            if msg_type == "subscribe":
                topic_name = msg.get("topic")
                client_id = msg.get("client_id")
                last_n = msg.get("last_n", 0)
                if not topic_name or not client_id:
                    await websocket.send_json(ws_error(
                        request_id, ERROR_BAD_REQUEST,
                        "subscribe requires topic and client_id",
                        ws_ts(),
                    ))
                    continue
                subscriber, err = registry.subscribe_to_topic_ws(topic_name, client_id)
                if err:
                    await websocket.send_json(ws_error(
                        request_id, ERROR_TOPIC_NOT_FOUND,
                        f"Topic {topic_name!r} not found",
                        ws_ts(),
                    ))
                    continue
                subscriber.set_send_callback(send_cb)
                subscriber.start_drain(asyncio.get_running_loop())
                current_connection_subscribers.add(subscriber)
                await websocket.send_json(ws_ack(request_id, topic_name, ws_ts()))
                if last_n and last_n > 0:
                    topic_obj = registry.get_topic(topic_name)
                    if topic_obj is not None:
                        for message, t in topic_obj.get_last_n(last_n):
                            event_msg = {"id": message.message_id, "payload": message.payload}
                            await websocket.send_json(ws_event(topic_name, event_msg, ws_ts()))
                continue

            if msg_type == "unsubscribe":
                topic = msg.get("topic")
                client_id = msg.get("client_id")
                if not topic or not client_id:
                    await websocket.send_json(ws_error(
                        request_id, ERROR_BAD_REQUEST,
                        "unsubscribe requires topic and client_id",
                        ws_ts(),
                    ))
                    continue
                ok = registry.unsubscribe_from_topic(topic, client_id)
                if not ok:
                    await websocket.send_json(ws_error(
                        request_id, ERROR_TOPIC_NOT_FOUND,
                        f"Topic {topic!r} not found or client not subscribed",
                        ws_ts(),
                    ))
                    continue
                await websocket.send_json(ws_ack(request_id, topic, ws_ts()))
                continue

            if msg_type == "publish":
                topic_name = msg.get("topic")
                message_body = msg.get("message")
                if not topic_name:
                    await websocket.send_json(ws_error(
                        request_id, ERROR_BAD_REQUEST,
                        "publish requires topic",
                        ws_ts(),
                    ))
                    continue
                if not message_body or not isinstance(message_body, dict):
                    await websocket.send_json(ws_error(
                        request_id, ERROR_BAD_REQUEST,
                        "publish requires message object with id and payload",
                        ws_ts(),
                    ))
                    continue
                topic = registry.get_topic(topic_name)
                if topic is None:
                    await websocket.send_json(ws_error(
                        request_id, ERROR_TOPIC_NOT_FOUND,
                        f"Topic {topic_name!r} not found",
                        ws_ts(),
                    ))
                    continue
                payload = message_body.get("payload")
                message_id = message_body.get("id")
                message = Message(
                    payload=payload,
                    topic_name=topic_name,
                    message_id=message_id,
                )
                topic.deliver(message)
                await websocket.send_json(ws_ack(request_id, topic_name, ws_ts()))
                continue

            await websocket.send_json(ws_error(
                request_id, ERROR_BAD_REQUEST,
                f"Unknown type: {msg_type!r}",
                ws_ts(),
            ))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json(ws_error(
                None, ERROR_INTERNAL,
                f"Unexpected server error: {e!s}",
                ws_ts(),
            ))
        except Exception:
            pass
    finally:
        for sub in current_connection_subscribers:
            sub.stop_drain()
            sub.set_send_callback(None)
        _ws_connections.discard(websocket)
