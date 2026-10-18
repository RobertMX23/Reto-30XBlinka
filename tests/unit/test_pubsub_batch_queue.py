from blinka.adapters.pubsub_batch_queue import PubSubBatchQueue, consume_batch_message


class Future:
    def result(self): return "msg-1"


class Publisher:
    def topic_path(self, project, topic): return f"projects/{project}/topics/{topic}"
    def publish(self, path, payload, **attrs):
        assert path.endswith("/blinka-batch")
        assert b'"batch_id":"B-1"' in payload
        assert attrs["batch_id"] == "B-1"
        return Future()


def test_publish_and_consume_validate_contract():
    queue = PubSubBatchQueue("project", publisher=Publisher())
    assert queue.publish_batch("B-1") == "msg-1"
    assert consume_batch_message('{"batch_id":"B-1"}', lambda batch_id: batch_id) == "B-1"
