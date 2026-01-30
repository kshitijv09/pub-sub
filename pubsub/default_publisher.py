"""Concrete Publisher implementation (in-memory, no broker)."""

from typing import Any, Optional

from pubsub.message import Message
from pubsub.publisher import Publisher
from pubsub.topic import Topic


class DefaultPublisher(Publisher):
    """Publisher that publishes in-memory directly to a topic."""

    def __init__(self, publisher_id: str) -> None:
        super().__init__(publisher_id)

    def publish(self, topic: Topic, payload: Any, **metadata: Any) -> Optional[Message]:
        """Create a message, notify observability, and deliver in-memory via topic."""
        message = Message(
            payload=payload,
            topic_name=topic.name,
            metadata=dict(metadata),
        )
        self.on_publish(message, topic)
        topic.deliver(message)
        return message
