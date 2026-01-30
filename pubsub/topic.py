"""Topic class for grouping subscribers and routing messages (in-memory only)."""

import os
import threading
from collections import deque
from typing import TYPE_CHECKING, List, Set, Tuple

if TYPE_CHECKING:
    from pubsub.message import Message
    from pubsub.subscriber import Subscriber

DEFAULT_RING_BUFFER_SIZE = 100


class Topic:
    """In-memory named channel; holds subscribers, delivers messages, and keeps a ring buffer for replay (last_n)."""

    def __init__(self, name: str, ring_buffer_size: int | None = None) -> None:
        self._name = name
        self._subscribers: Set["Subscriber"] = set()
        self._messages_delivered: int = 0
        self._lock = threading.Lock()
        try:
            size = int(os.environ.get("TOPIC_RING_BUFFER_SIZE", DEFAULT_RING_BUFFER_SIZE))
        except (ValueError, TypeError):
            size = ring_buffer_size or DEFAULT_RING_BUFFER_SIZE
        self._ring: deque = deque(maxlen=max(1, size))

    @property
    def name(self) -> str:
        return self._name

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    @property
    def messages_delivered(self) -> int:
        return self._messages_delivered

    def subscribe(self, subscriber: "Subscriber") -> None:
        """Add a subscriber to this topic."""
        with self._lock:
            self._subscribers.add(subscriber)

    def unsubscribe(self, subscriber: "Subscriber") -> None:
        """Remove a subscriber from this topic."""
        with self._lock:
            self._subscribers.discard(subscriber)

    def get_subscribers(self) -> List["Subscriber"]:
        """Return a copy of the subscriber list (under lock)."""
        with self._lock:
            return list(self._subscribers)

    def deliver(self, message: "Message") -> None:
        """Deliver a message in-memory to all subscribers of this topic. Copy subscriber list under lock, then deliver without holding lock."""
        from pubsub.observability import get_logger

        logger = get_logger("pubsub.topic")
        with self._lock:
            subscribers = list(self._subscribers)
        logger.info(
            "delivering",
            extra={
                "topic": self._name,
                "message_id": message.message_id,
                "subscriber_count": len(subscribers),
            },
        )
        self._messages_delivered += 1
        with self._lock:
            self._ring.append(message)
        for subscriber in subscribers:
            try:
                subscriber.deliver_message(message, self)
            except Exception as e:
                logger.exception(
                    "delivery_failed",
                    extra={
                        "subscriber_id": subscriber.subscriber_id,
                        "message_id": message.message_id,
                        "error": str(e),
                    },
                )

    def get_last_n(self, n: int) -> List[Tuple["Message", "Topic"]]:
        """Return the last n messages (oldest first) for replay. Thread-safe."""
        if n <= 0:
            return []
        with self._lock:
            buf = list(self._ring)
        k = min(n, len(buf))
        if k == 0:
            return []
        return [(msg, self) for msg in buf[-k:]]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Topic):
            return False
        return self._name == other._name

    def __hash__(self) -> int:
        return hash(self._name)

    def __repr__(self) -> str:
        return f"Topic(name={self._name!r}, subscribers={len(self._subscribers)})"
