"""Abstract Subscriber and base implementation for observability."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pubsub.observability import get_logger

if TYPE_CHECKING:
    from pubsub.message import Message
    from pubsub.topic import Topic


class Subscriber(ABC):
    """Abstract base class for subscribers that receive messages from topics."""

    def __init__(self, subscriber_id: str) -> None:
        self._subscriber_id = subscriber_id
        self._logger = get_logger(f"pubsub.subscriber.{subscriber_id}")

    @property
    def subscriber_id(self) -> str:
        return self._subscriber_id

    @abstractmethod
    def on_message(self, message: "Message", topic: "Topic") -> None:
        """Handle a message delivered for a topic. Must be implemented by subclasses."""
        pass

    def deliver_message(self, message: "Message", topic: "Topic") -> None:
        """Called by Topic.deliver(); default implementation calls on_message. Override to enqueue instead."""
        self.on_message(message, topic)

    def on_subscribe(self, topic: "Topic") -> None:
        """Called when this subscriber is added to a topic (for observability)."""
        self._logger.info(
            "subscribed",
            extra={"topic": topic.name, "subscriber_id": self._subscriber_id},
        )

    def on_unsubscribe(self, topic: "Topic") -> None:
        """Called when this subscriber is removed from a topic (for observability)."""
        self._logger.info(
            "unsubscribed",
            extra={"topic": topic.name, "subscriber_id": self._subscriber_id},
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self._subscriber_id!r})"
