from blinka.adapters.firestore_batch_store import FirestoreBatchStore
from blinka.domain.batch_models import BatchItem, BatchRequest, BatchState
from blinka.domain.input_models import InputRequest


class Snapshot:
    def __init__(self, data=None):
        self._data, self.exists = data, data is not None
    def to_dict(self):
        return self._data


class Document:
    def __init__(self): self.data = None
    def get(self): return Snapshot(self.data)
    def set(self, payload, merge=False):
        self.data = {**(self.data or {}), **payload} if merge else payload


class Collection:
    def __init__(self): self.docs = {}
    def document(self, key): return self.docs.setdefault(key, Document())


class Client:
    def __init__(self): self.collections = {}
    def collection(self, name): return self.collections.setdefault(name, Collection())


def test_firestore_store_round_trips_structured_batch():
    store = FirestoreBatchStore(client=Client())
    request = BatchRequest(batch_id="FS-1", items=[BatchItem(document_id="D-1", request=InputRequest(content="x"))])
    created = store.create(request)
    assert created.state == BatchState.RECEIVED
    store.save(created.model_copy(update={"state": BatchState.PROCESSING}))
    assert store.get("FS-1").state == BatchState.PROCESSING
