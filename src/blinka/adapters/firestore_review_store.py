from __future__ import annotations
from typing import Any
from blinka.domain.review_models import HumanReview, ReviewDecision
from blinka.errors import StorageError

class FirestoreReviewStore:
    def __init__(self, collection="human_reviews", *, client: Any | None = None):
        self.collection_name, self.client = collection, client
    def _collection(self):
        if self.client is None:
            from google.cloud import firestore
            self.client = firestore.Client()
        return self.client.collection(self.collection_name)
    def create(self, review: HumanReview) -> HumanReview:
        try:
            ref=self._collection().document(review.review_id)
            if not ref.get().exists: ref.set(review.model_dump(mode="json"))
            return self.get(review.review_id) or review
        except Exception as exc: raise StorageError(f"No se pudo crear revisión: {exc}") from exc
    def get(self, review_id: str) -> HumanReview | None:
        snap=self._collection().document(review_id).get()
        return HumanReview.model_validate(snap.to_dict()) if snap.exists else None
    def list_pending(self) -> list[HumanReview]:
        return [HumanReview.model_validate(s.to_dict()) for s in self._collection().where("state", "==", "WAITING_HUMAN_APPROVAL").stream()]
    def decide(self, review_id: str, decision: ReviewDecision, decided_by: str, reason: str | None = None) -> HumanReview:
        review=self.get(review_id)
        if review is None: raise KeyError(review_id)
        updated=review.model_copy(update={"decision": decision, "state": "PAGAR" if decision == ReviewDecision.APPROVE else "FRENAR", "decided_by": decided_by, "reason": reason or review.reason})
        self._collection().document(review_id).set(updated.model_dump(mode="json"))
        return updated
