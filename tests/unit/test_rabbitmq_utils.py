from __future__ import annotations

from types import SimpleNamespace

from app.utils import rabbitmq


def test_publish_parsing_task_success(monkeypatch):
    class _Channel:
        def queue_declare(self, queue, durable):
            assert queue == "parsing_tasks"
            assert durable is True

        def basic_publish(self, exchange, routing_key, body, properties):
            assert routing_key == "parsing_tasks"
            assert body

    class _Conn:
        def channel(self):
            return _Channel()

        def close(self):
            return None

    monkeypatch.setattr(rabbitmq, "get_settings", lambda: SimpleNamespace(rabbitmq_url="amqp://guest:guest@localhost/"))
    monkeypatch.setattr(rabbitmq.pika, "URLParameters", lambda url: url)
    monkeypatch.setattr(rabbitmq.pika, "BlockingConnection", lambda params: _Conn())
    monkeypatch.setattr(rabbitmq.pika, "BasicProperties", lambda delivery_mode: {"delivery_mode": delivery_mode})
    assert rabbitmq.publish_parsing_task({"a": 1}) is True


def test_publish_parsing_task_failure(monkeypatch):
    monkeypatch.setattr(rabbitmq, "get_settings", lambda: SimpleNamespace(rabbitmq_url="amqp://bad/"))
    monkeypatch.setattr(rabbitmq.pika, "URLParameters", lambda url: url)

    def _boom(_params):
        raise RuntimeError("nope")

    monkeypatch.setattr(rabbitmq.pika, "BlockingConnection", _boom)
    assert rabbitmq.publish_parsing_task({"a": 1}) is False

