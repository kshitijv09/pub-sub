# Pub-Sub System (Python) with Observability

In-memory pub-sub with abstract **Publisher** and **Subscriber**, **Topic** and **Message** classes, and observability. No broker; topics hold subscribers and deliver messages in memory.

## Structure

```
pub-sub/
├── pubsub/
│   ├── __init__.py
│   ├── message.py          # Message (payload, topic, metadata, timestamp)
│   ├── topic.py            # Topic (name, subscribers, deliver in-memory)
│   ├── publisher.py        # Abstract Publisher
│   ├── subscriber.py       # Abstract Subscriber
│   ├── default_publisher.py
│   ├── default_subscriber.py
│   └── observability/
│       ├── __init__.py
│       ├── logger.py       # Structured logging
│       └── metrics.py      # Counters/gauges
├── example.py
├── requirements.txt
└── README.md
```

## Usage

```python
from pubsub import Topic, DefaultPublisher, DefaultSubscriber

topic = Topic("orders")

pub = DefaultPublisher("p1")
sub = DefaultSubscriber("s1")
topic.subscribe(sub)

pub.publish(topic, {"order_id": 42})
# Message is delivered in-memory to sub; observability logs publish and delivery.
```

## Extending

- **Publisher**: Subclass `Publisher`, implement `publish(topic, payload, **metadata)` and call `on_publish` for observability.
- **Subscriber**: Subclass `Subscriber`, implement `on_message(message, topic)`; use `on_subscribe`/`on_unsubscribe` for observability.
