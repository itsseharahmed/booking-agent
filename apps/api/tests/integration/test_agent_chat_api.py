"""Tests for authenticated persistent agent conversations."""

from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from sqlalchemy.orm import Session

from optometry.api.agent_chat import router
from optometry.auth.dependencies import get_current_patient
from optometry.db.models.patient import Patient
from optometry.db.session import get_db


class FakeGraph:
    def __init__(self) -> None:
        self.calls: list[list[Any]] = []

    def invoke(
        self,
        state: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        messages = state["messages"]
        self.calls.append(messages)

        assert config["recursion_limit"] == 12

        return {
            "messages": [
                *messages,
                AIMessage(content="I can help with your appointment."),
            ]
        }


def create_test_patient(db: Session, email: str) -> Patient:
    patient = Patient(
        first_name="Test",
        last_name="Patient",
        email=email,
        password_hash="unused-test-hash",
        is_active=True,
    )
    db.add(patient)
    db.flush()
    return patient


# checks messages persist across separate HTTP requests
def test_chat_preserves_conversation(
    test_session: Session,
    monkeypatch: Any,
) -> None:
    patient = create_test_patient(
        test_session,
        f"agent-chat-{uuid4()}@example.com",
    )

    graph = FakeGraph()

    monkeypatch.setattr(
        "optometry.api.agent_chat.create_agent_model",
        lambda: object(),
    )
    monkeypatch.setattr(
        "optometry.api.agent_chat.build_read_only_graph",
        lambda _model: graph,
    )

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_db] = lambda: test_session
    app.dependency_overrides[get_current_patient] = lambda: patient

    with TestClient(app) as client:
        first = client.post(
            "/agent/chat",
            json={"message": "Hello"},
        )

        assert first.status_code == 200
        conversation_id = first.json()["conversation_id"]

        second = client.post(
            "/agent/chat",
            json={
                "message": "Find an appointment",
                "conversation_id": conversation_id,
            },
        )

        assert second.status_code == 200

    assert second.json()["conversation_id"] == conversation_id
    assert first.json()["proposal"] is None
    assert len(graph.calls) == 2
    assert len(graph.calls[0]) == 1
    assert len(graph.calls[1]) == 3


# checks patients have isolated conversation histories
def test_chat_isolates_patients(
    test_session: Session,
    monkeypatch: Any,
) -> None:
    patient_a = create_test_patient(
        test_session,
        f"agent-a-{uuid4()}@example.com",
    )
    patient_b = create_test_patient(
        test_session,
        f"agent-b-{uuid4()}@example.com",
    )

    graph = FakeGraph()

    monkeypatch.setattr(
        "optometry.api.agent_chat.create_agent_model",
        lambda: object(),
    )
    monkeypatch.setattr(
        "optometry.api.agent_chat.build_read_only_graph",
        lambda _model: graph,
    )

    app = FastAPI()
    app.include_router(router)

    current_patient = {"value": patient_a}

    app.dependency_overrides[get_db] = lambda: test_session
    app.dependency_overrides[get_current_patient] = lambda: current_patient["value"]

    shared_id = str(uuid4())

    with TestClient(app) as client:
        first = client.post(
            "/agent/chat",
            json={
                "message": "Patient A private message",
                "conversation_id": shared_id,
            },
        )
        assert first.status_code == 200

        current_patient["value"] = patient_b

        second = client.post(
            "/agent/chat",
            json={
                "message": "Patient B message",
                "conversation_id": shared_id,
            },
        )

        assert second.status_code == 200

    assert len(graph.calls[0]) == 1
    assert len(graph.calls[1]) == 1
    assert "Patient A private message" not in str(graph.calls[1])


# checks authentication is required
def test_agent_chat_requires_authentication() -> None:
    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.post(
            "/agent/chat",
            json={"message": "Hello"},
        )

    assert response.status_code == 401


# checks input validation
def test_agent_chat_rejects_invalid_message() -> None:
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_current_patient] = lambda: type(
        "PatientStub", (), {"id": 7}
    )()

    with TestClient(app) as client:
        response = client.post(
            "/agent/chat",
            json={
                "message": "",
                "conversation_id": str(UUID(int=1)),
            },
        )

    assert response.status_code == 422


# checks chat confirmation never reports an executed booking
def test_chat_cannot_confirm_booking(
    test_session: Session,
    monkeypatch: Any,
) -> None:
    patient = create_test_patient(
        test_session,
        f"agent-confirm-{uuid4()}@example.com",
    )

    class MisleadingGraph:
        def invoke(
            self,
            state: dict[str, Any],
            config: dict[str, Any],
        ) -> dict[str, Any]:
            return {
                "messages": [
                    *state["messages"],
                    AIMessage(content="Your appointment has been confirmed."),
                ]
            }

    monkeypatch.setattr(
        "optometry.api.agent_chat.create_agent_model",
        lambda: object(),
    )
    monkeypatch.setattr(
        "optometry.api.agent_chat.build_read_only_graph",
        lambda _model: MisleadingGraph(),
    )

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[get_db] = lambda: test_session
    app.dependency_overrides[get_current_patient] = lambda: patient

    with TestClient(app) as client:
        response = client.post(
            "/agent/chat",
            json={"message": "confirm"},
        )

    assert response.status_code == 200
    assert "has not been booked" in response.json()["response"]
    assert response.json()["proposal"] is None
