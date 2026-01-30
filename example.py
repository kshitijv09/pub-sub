"""Example: in-memory pub-sub with observability (no broker)."""

import logging

from pubsub import DefaultPublisher, DefaultSubscriber, Topic

logging.basicConfig(level=logging.INFO)


def main() -> None:
    topic = Topic("events")

    publisher = DefaultPublisher("producer-1")
    subscriber = DefaultSubscriber("consumer-1")
    topic.subscribe(subscriber)
    subscriber.on_subscribe(topic)

    publisher.publish(topic, {"event": "user.signup", "user_id": 101})
    publisher.publish(topic, {"event": "order.placed", "order_id": 201})

    topic.unsubscribe(subscriber)
    subscriber.on_unsubscribe(topic)


if __name__ == "__main__":
    main()
