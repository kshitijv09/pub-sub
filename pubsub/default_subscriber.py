"""Concrete Subscriber implementation with observability hooks."""

from pubsub.message import Message
from pubsub.subscriber import Subscriber
from pubsub.topic import Topic


class DefaultSubscriber(Subscriber):
    """Subscriber that logs and optionally processes messages (override on_message)."""

    def on_message(self, message: Message, topic: Topic) -> None:
        """Log delivery and payload; subclasses can override for custom handling."""
        self._logger.info(
            "message_received",
            extra={
                "topic": topic.name,
                "message_id": message.message_id,
                "payload_type": type(message.payload).__name__,
            },
        )
