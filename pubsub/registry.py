"""In-memory topic and subscriber registry for the server."""

import uuid
from typing import Dict, List, Optional, Tuple

from pubsub.topic import Topic
from pubsub.client_subscriber import ClientSubscriber
from pubsub.protocol import ws_info, ws_ts


class Registry:
    """In-memory registry of topics and client subscribers (for HTTP/WS)."""

    def __init__(self) -> None:
        self._topics: Dict[str, Topic] = {}
        self._subscribers: Dict[str, ClientSubscriber] = {}

    def create_topic(self, name: str) -> Tuple[Optional[Topic], bool]:
        """
        Create a topic only if it does not exist.
        Returns (topic, True) on success, (None, False) if topic already exists (conflict).
        """
        if name in self._topics:
            return None, False
        topic = Topic(name)
        self._topics[name] = topic
        return topic, True

    def delete_topic(self, name: str) -> bool:
        """
        Notify subscribers with info topic_deleted, unsubscribe all, then remove the topic.
        Returns True if topic existed and was deleted, False if not found (404).
        """
        topic = self._topics.get(name)
        if topic is None:
            return False
        ts = ws_ts()
        for subscriber in topic.get_subscribers():
            if hasattr(subscriber, "send"):
                subscriber.send(ws_info("topic_deleted", ts, topic.name))
            topic.unsubscribe(subscriber)
            subscriber.on_unsubscribe(topic)
        del self._topics[name]
        return True

    def unsubscribe_from_topic(self, topic_name: str, client_id: str) -> bool:
        """
        Remove client from topic. Returns True if client was subscribed and removed.
        """
        topic = self._topics.get(topic_name)
        if topic is None:
            return False
        subscriber = self._subscribers.get(client_id)
        if subscriber is None:
            return False
        if subscriber not in topic.get_subscribers():
            return False
        topic.unsubscribe(subscriber)
        subscriber.on_unsubscribe(topic)
        return True

    def list_topics(self) -> List[Dict[str, int]]:
        """Return list of {name, subscribers} for each topic."""
        return [
            {"name": t.name, "subscribers": t.subscriber_count}
            for t in self._topics.values()
        ]

    def topic_stats(self) -> Dict[str, Dict[str, int]]:
        """Return { topic_name: { messages, subscribers } } for stats endpoint."""
        return {
            name: {
                "messages": topic.messages_delivered,
                "subscribers": topic.subscriber_count,
            }
            for name, topic in self._topics.items()
        }

    def get_or_create_topic(self, name: str) -> Topic:
        """Return existing topic or create and register a new one."""
        if name not in self._topics:
            self._topics[name] = Topic(name)
        return self._topics[name]

    def get_topic(self, name: str) -> Optional[Topic]:
        """Return topic by name or None."""
        return self._topics.get(name)

    def topic_count(self) -> int:
        """Number of topics."""
        return len(self._topics)

    def total_subscriber_count(self) -> int:
        """Total number of registered client subscribers (may be on multiple topics)."""
        return len(self._subscribers)

    def subscribe_to_topic(
        self,
        topic_name: str,
        subscriber_id: Optional[str] = None,
    ) -> ClientSubscriber:
        """
        Create or get a client subscriber, add to topic, return subscriber.
        subscriber_id is optional; one is generated if not provided.
        """
        topic = self.get_or_create_topic(topic_name)
        sid = subscriber_id or f"sub_{uuid.uuid4().hex[:8]}"
        if sid in self._subscribers:
            subscriber = self._subscribers[sid]
        else:
            subscriber = ClientSubscriber(sid)
            self._subscribers[sid] = subscriber
        topic.subscribe(subscriber)
        subscriber.on_subscribe(topic)
        return subscriber

    def subscribe_to_topic_ws(
        self,
        topic_name: str,
        client_id: str,
    ) -> Tuple[Optional[ClientSubscriber], Optional[str]]:
        """
        Subscribe client to topic over WS. Topic must exist.
        Returns (subscriber, None) on success, (None, "TOPIC_NOT_FOUND") if topic missing.
        """
        topic = self.get_topic(topic_name)
        if topic is None:
            return None, "TOPIC_NOT_FOUND"
        if client_id in self._subscribers:
            subscriber = self._subscribers[client_id]
        else:
            subscriber = ClientSubscriber(client_id)
            self._subscribers[client_id] = subscriber
        topic.subscribe(subscriber)
        subscriber.on_subscribe(topic)
        return subscriber, None

    def get_subscriber(self, subscriber_id: str) -> Optional[ClientSubscriber]:
        """Return client subscriber by id or None."""
        return self._subscribers.get(subscriber_id)
