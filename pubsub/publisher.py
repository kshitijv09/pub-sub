"""Abstract Publisher and base implementation for observability."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

from pubsub.observability import get_logger

if TYPE_CHECKING:
    from pubsub.message import Message
    from pubsub.topic import Topic


class Publisher(ABC):
    """Abstract base class for publishers that send messages to topics."""

    def __init__(self, publisher_id: str) -> None:
        self._publisher_id = publisher_id
        self._logger = get_logger(f"pubsub.publisher.{publisher_id}")

    @property
    def publisher_id(self) -> str:
        return self._publisher_id

    @abstractmethod
    def publish(self, topic: "Topic", payload: Any, **metadata: Any) -> Optional["Message"]:
        """
        Publish a message to a topic. Must be implemented by subclasses.
        Returns the published Message or None.
        """
        pass

    def on_publish(self, message: "Message", topic: "Topic") -> None:
        """Called after a message is published (for observability)."""
        self._logger.info(
            "published",
            extra={
                "topic": topic.name,
                "message_id": message.message_id,
                "publisher_id": self._publisher_id,
            },
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self._publisher_id!r})"
