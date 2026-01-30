"""Client subscriber for socket/WS: per-consumer queue (thread-safe queue.Queue), drain task sends events via callback."""

import asyncio
import queue
from typing import Callable, Dict, Any, TYPE_CHECKING

from pubsub.subscriber import Subscriber

if TYPE_CHECKING:
    from pubsub.message import Message
    from pubsub.topic import Topic

# Sentinel to unblock drain_loop when stopping
_DRAIN_SENTINEL = (None, None)

# Default max messages per consumer queue (env SUBSCRIBER_QUEUE_MAX_SIZE overrides)
DEFAULT_QUEUE_MAX_SIZE = 1024


class ClientSubscriber(Subscriber):
    """Subscriber with a per-consumer queue (queue.Queue); messages are enqueued and drained to the send callback."""

    def __init__(self, client_id: str, queue_max_size: int | None = None) -> None:
        super().__init__(client_id)
        self._send_callback: Callable[[Dict[str, Any]], None] | None = None
        try:
            import os
            max_size = int(os.environ.get("SUBSCRIBER_QUEUE_MAX_SIZE", DEFAULT_QUEUE_MAX_SIZE))
        except (ValueError, TypeError):
            max_size = queue_max_size or DEFAULT_QUEUE_MAX_SIZE
        self._queue: queue.Queue = queue.Queue(maxsize=max_size)
        self._drain_task: asyncio.Task | None = None
        self._closed = False

    def set_send_callback(self, callback: Callable[[Dict[str, Any]], None] | None) -> None:
        """Set or clear the callback that sends a JSON-serializable dict (e.g. WS event/info)."""
        self._send_callback = callback
        if callback is None:
            self.stop_drain()

    def send(self, payload: Dict[str, Any]) -> None:
        """Send a server message (event, info, etc.) via callback if set."""
        if self._send_callback is not None:
            self._send_callback(payload)

    def deliver_message(self, message: "Message", topic: "Topic") -> None:
        """Enqueue (message, topic) for this consumer; drain_loop sends to client. On queue full, drop oldest and enqueue new. Thread-safe (queue.Queue)."""
        if self._closed:
            return
        try:
            self._queue.put((message, topic), block=False)
        except queue.Full:
            try:
                dropped_msg, dropped_topic = self._queue.get(block=False)
                self._queue.put((message, topic), block=False)
                self._logger.warning(
                    "queue_full_dropped_oldest",
                    extra={
                        "topic": topic.name,
                        "dropped_message_id": getattr(dropped_msg, "message_id", None),
                        "client_id": self.subscriber_id,
                    },
                )
            except (queue.Full, queue.Empty):
                self._logger.exception("queue_evict_failed", extra={"client_id": self.subscriber_id})

    def on_message(self, message: "Message", topic: "Topic") -> None:
        """Used when draining from queue: build event and send via callback; also used by send() for info."""
        if self._send_callback is not None:
            event_msg = {"id": message.message_id, "payload": message.payload}
            from pubsub.protocol import ws_event, ws_ts
            self._send_callback(ws_event(topic.name, event_msg, ws_ts()))
        self._logger.info(
            "message_received",
            extra={
                "topic": topic.name,
                "message_id": message.message_id,
                "client_id": self.subscriber_id,
            },
        )

    async def drain_loop(self) -> None:
        """Consume from this subscriber's queue (blocking get in executor) and send events via callback until closed."""
        loop = asyncio.get_running_loop()
        while not self._closed:
            try:
                message, topic = await loop.run_in_executor(None, self._queue.get)
                if message is None and topic is None:
                    break
                self.on_message(message, topic)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.exception("drain_error", extra={"error": str(e)})

    def start_drain(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start the drain task (idempotent). Call when send_callback is set."""
        if self._drain_task is not None and not self._drain_task.done():
            return
        self._closed = False
        self._drain_task = loop.create_task(self.drain_loop())

    def stop_drain(self) -> None:
        """Unblock drain and mark closed. Puts sentinel so blocking queue.get() returns."""
        self._closed = True
        try:
            self._queue.put(_DRAIN_SENTINEL, block=False)
        except queue.Full:
            pass
        if self._drain_task is not None:
            self._drain_task.cancel()
            self._drain_task = None
