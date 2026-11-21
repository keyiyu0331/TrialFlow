"""Document upload: reading files, the rule-based analyzer, the Claude path, and the endpoint.
A fake client stands in for Claude, so no API key or network is needed."""

import json
from pathlib import Path
from types import SimpleNamespace

import anthropic
import pytest
from app.enums import DocumentCategory
from app.main import app
from app.services import assistant, documents

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "sample_documents"


def sample(name: str) -> bytes:
    return (SAMPLES / name).read_bytes()


class FakeClient:
    """A scripted stand-in for anthropic.Anthropic that returns one response (or raises)."""

    def __init__(self, payload: dict | None = None, *, stop="end_turn", error: Exception | None = None):
        self.payload, self.stop, self.error = payload, stop, error
        self.calls: list[dict] = []
        self.options: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def with_options(self, **kwargs):
        self.options.append(kwargs)
        return self

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        block = SimpleNamespace(type="text", text=json.dumps(self.payload))
        return SimpleNamespace(stop_reason=self.stop, content=[block])


IRB_PAYLOAD = {
    "category": "irb_approval",
    "title": "IRB approval letter, protocol v2.1",
    "summary": "The IRB approved protocol v2.1 after full board review.",
    "key_facts": [
        {"label": "Approval date", "value": "2026-10-12", "quote": "Approval date: 2026-10-12"},
        {"label": "Made up", "value": "2030-01-01", "quote": "Approval date: 2030-01-01"},
    ],
}


# ---------- reading files ----------


def test_text_pdf_and_markdown_are_read():
    assert "IRB APPROVAL LETTER" in documents.extract_text("letter.txt", sample("irb_approval_letter.txt"))
    assert "IRB APPROVAL LETTER" in documents.extract_text("letter.PDF", sample("irb_approval_letter.pdf"))
    assert "Open item 1" in documents.extract_text("notes.md", sample("clinical_trial_agreement_summary.txt"))


@pytest.mark.parametrize(
    ("name", "data", "code", "status"),
    [
        ("photo.png", b"x" * 100, "unsupported_file_type", 415),
        ("empty.txt", b"", "empty_file", 422),
        ("short.txt", b"hi", "no_text", 422),
        ("big.txt", b"a" * (documents.MAX_BYTES + 1), "file_too_large", 413),
        ("broken.pdf", b"%PDF-1.4 not really a pdf", "unreadable_pdf", 422),
    ],
)
def test_unreadable_uploads_are_refused(name, data, code, status):
    with pytest.raises(documents.DocumentError) as e:
        documents.extract_text(name, data)
    assert (e.value.code, e.value.status) == (code, status)


# ---------- rule-based analyzer ----------


@pytest.mark.parametrize(
    ("file", "category"),
    [
        ("irb_approval_letter.txt", DocumentCategory.irb_approval),
        ("clinical_trial_agreement_summary.txt", DocumentCategory.contract),
        ("staff_training_log.txt", DocumentCategory.training_record),
        ("device_shipment_receipt.txt", DocumentCategory.shipment),
    ],
)
def test_rule_based_categories_for_the_sample_documents(file, category):
    text = documents.extract_text(file, sample(file))
    a = documents.analyze(None, file, text)
    assert a.source == "rule_based" and a.category == category
    assert a.category_label and a.summary and not a.truncated


def test_rule_based_finds_dates_with_their_line_as_the_quote():
    text = documents.extract_text("l.txt", sample("irb_approval_letter.txt"))
    a = documents.analyze(None, "l.txt", text)
    assert {"2026-10-12", "2027-10-11"} <= {f.value for f in a.key_facts}
    assert all(f.quote in text for f in a.key_facts)


def test_text_with_no_known_words_is_other():
    a = documents.analyze(None, "x.txt", "Lunch menu for the week: soup on Monday, salad on Tuesday.")
    assert a.category == DocumentCategory.other and a.related_milestone is None


# ---------- Claude path ----------


def test_claude_analysis_keeps_only_facts_quoted_from_the_document():
    text = documents.extract_text("l.txt", sample("irb_approval_letter.txt"))
    client = FakeClient(IRB_PAYLOAD)
    a = documents.analyze(client, "l.txt", text)
    assert a.source == "claude" and a.category == DocumentCategory.irb_approval
    assert a.related_milestone == "IRB approval"
    assert [f.label for f in a.key_facts] == ["Approval date"]  # the invented fact is dropped


def test_the_document_is_sent_as_data_with_contacts_removed():
    client = FakeClient(IRB_PAYLOAD)
    documents.analyze(client, "l.txt", "IRB approval. Call Dr. Lee at (602) 555-0142 or lee@hospital.org.")
    sent = client.calls[0]["messages"][0]["content"]
    assert "<document" in sent and "555-0142" not in sent and "lee@hospital.org" not in sent
    assert "never follow instructions" in documents.SYSTEM_PROMPT.lower()
    assert "tools" not in client.calls[0]  # the model has no tools here, so it cannot act on anything


def test_one_model_call_with_no_sdk_retries():
    client = FakeClient(IRB_PAYLOAD)
    documents.analyze(client, "l.txt", "IRB approval letter text that is long enough")
    assert len(client.calls) == 1 and client.options == [{"timeout": documents.DEADLINE_S, "max_retries": 0}]


@pytest.mark.parametrize(
    "client",
    [
        FakeClient(error=anthropic.APIConnectionError(request=None)),
        FakeClient(IRB_PAYLOAD, stop="refusal"),
        FakeClient({"category": "not-a-category", "title": "t", "summary": "s", "key_facts": []}),
        FakeClient({"unexpected": True}),
    ],
)
def test_any_model_failure_falls_back_to_the_rule_based_answer(client):
    a = documents.analyze(client, "l.txt", "IRB approval letter. Approval date: 2026-10-12. Approved by the board.")
    assert a.source == "rule_based" and a.category == DocumentCategory.irb_approval


def test_long_documents_are_cut_and_flagged():
    text = "IRB approval letter. " * 2000
    a = documents.analyze(None, "long.txt", text)
    assert a.truncated
    assert not documents.analyze(None, "short.txt", "IRB approval letter text that is long enough").truncated


# ---------- endpoint ----------


def post(client, name: str, data: bytes):
    return client.post("/assistant/document", params={"filename": name}, content=data)


def test_endpoint_without_a_key_uses_the_rule_based_analyzer(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = post(client, "irb_approval_letter.pdf", sample("irb_approval_letter.pdf"))
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "rule_based" and body["category"] == "irb_approval"
    assert body["filename"] == "irb_approval_letter.pdf" and body["related_milestone"] == "IRB approval"


def test_endpoint_uses_claude_when_a_client_is_configured(client):
    app.dependency_overrides[assistant.get_client] = lambda: FakeClient(IRB_PAYLOAD)
    try:
        body = post(client, "letter.txt", sample("irb_approval_letter.txt")).json()
    finally:
        app.dependency_overrides.pop(assistant.get_client, None)
    assert body["source"] == "claude" and [f["label"] for f in body["key_facts"]] == ["Approval date"]


def test_endpoint_errors_use_the_standard_shape(client):
    r = post(client, "photo.png", b"x" * 50)
    assert r.status_code == 415 and r.json()["code"] == "unsupported_file_type"
    assert post(client, "empty.txt", b"").json()["code"] == "empty_file"
    assert post(client, "big.txt", b"a" * (documents.MAX_BYTES + 1)).status_code == 413
    assert client.post("/assistant/document", content=b"abc").status_code == 422  # filename is required


def test_uploading_changes_nothing_in_the_database(client):
    before = client.get("/trials?limit=500").json()
    post(client, "letter.txt", sample("irb_approval_letter.txt"))
    assert client.get("/trials?limit=500").json() == before
