"""Message class for pub-sub payload and metadata."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Message:
    """Represents a message published to a topic."""

    payload: Any
    topic_name: str
    message_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.message_id is None:
            self.message_id = f"{self.topic_name}_{id(self)}_{self.timestamp.timestamp()}"

    def to_dict(self) -> dict:
        """Serialize message for logging or transport."""
        return {
            "message_id": self.message_id,
            "topic_name": self.topic_name,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "metadata": self.metadata,
        }
