import { useState, type FormEvent } from "react";
import "./App.css";

type BookingProposal = {
  action: "book";
  clinic_id: number;
  optometrist_id: number;
  service_id: number;
  start_at: string;
  requires_confirmation: true;
};

type CancellationProposal = {
  action: "cancel";
  appointment_id: number;
  requires_confirmation: true;
};

type Proposal = BookingProposal | CancellationProposal;

type ChatResponse = {
  conversation_id: string;
  response: string;
  proposal: Proposal | null;
};

type PreparedConfirmation = {
  confirmation_token: string;
  action: "book" | "cancel";
  expires_in_seconds: number;
  details: Record<string, string | number>;
};

type ChatMessage = {
  role: "patient" | "assistant";
  content: string;
};

async function apiRequest<T>(
  path: string,
  token: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body === undefined
        ? {}
        : { "Content-Type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;

    try {
      const data = (await response.json()) as { detail?: unknown };

      if (typeof data.detail === "string") {
        message = data.detail;
      }
    } catch {
      //keep the generic error
    }

    throw new Error(message);
  }

  return (await response.json()) as T;
}

function App() {
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [prepared, setPrepared] = useState<PreparedConfirmation | null>(null);
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState("");

  function resetConversation() {
    setConversationId(null);
    setMessages([]);
    setProposal(null);
    setPrepared(null);
    setApproved(false);
    setError("");
    setResult("");
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!message.trim() || !token.trim() || busy) return;

    const userMessage = message.trim();

    setBusy(true);
    setError("");
    setResult("");
    setProposal(null);
    setPrepared(null);
    setApproved(false);
    setMessage("");

    setMessages((previous) => [
      ...previous,
      { role: "patient", content: userMessage },
    ]);

    try {
      const data = await apiRequest<ChatResponse>(
        "/agent/chat",
        token,
        {
          message: userMessage,
          ...(conversationId ? { conversation_id: conversationId } : {}),
        },
      );

      setConversationId(data.conversation_id);
      setMessages((previous) => [
        ...previous,
        { role: "assistant", content: data.response },
      ]);
      setProposal(data.proposal);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Chat request failed",
      );
    } finally {
      setBusy(false);
    }
  }

  async function prepareAction() {
    if (!proposal || busy) return;

    setBusy(true);
    setError("");

    try {
      const data = await apiRequest<PreparedConfirmation>(
        "/agent/confirmations/prepare",
        token,
        proposal,
      );

      setPrepared(data);
      setApproved(false);
      setProposal(null);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not prepare confirmation",
      );
    } finally {
      setBusy(false);
    }
  }

  async function approveAction() {
    if (!prepared || busy) return;

    setBusy(true);
    setError("");

    try {
      await apiRequest<{ approved: boolean }>(
        `/agent/confirmations/${encodeURIComponent(
          prepared.confirmation_token,
        )}/approve`,
        token,
      );

      setApproved(true);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Approval failed",
      );
    } finally {
      setBusy(false);
    }
  }

  async function executeAction() {
    if (!prepared || !approved || busy) return;

    setBusy(true);
    setError("");

    try {
      const data = await apiRequest<Record<string, unknown>>(
        `/agent/confirmations/${encodeURIComponent(
          prepared.confirmation_token,
        )}/execute/${prepared.action}`,
        token,
      );

      const appointmentId = data.appointment_id;

      setResult(
        prepared.action === "book"
          ? `Appointment ${appointmentId} booked successfully.`
          : `Appointment ${appointmentId} cancelled successfully.`,
      );

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content:
            prepared.action === "book"
              ? `Booking completed. Appointment ID: ${appointmentId}.`
              : `Cancellation completed. Appointment ID: ${appointmentId}.`,
        },
      ]);

      setPrepared(null);
      setApproved(false);
      setConversationId(null);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Execution failed",
      );

      //execution may have succeeded even if the response was lost
      //never automatically retry an uncertain write
      setPrepared(null);
      setApproved(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="booking-app">
      <h1>Optometry Booking</h1>
      <p>Authenticated appointment assistant</p>

      <section className="panel">
        <h2>Patient authentication</h2>

        <label htmlFor="patient-token">Patient access token</label>
        <input
          id="patient-token"
          type="password"
          autoComplete="off"
          value={token}
          onChange={(event) => {
            setToken(event.target.value);
            resetConversation();
          }}
          placeholder="Paste your patient JWT"
        />

        <p className="hint">
          Development only. The token is held in page memory.
          Do not use an admin token.
        </p>
      </section>

      <section className="panel">
        <h2>Appointment assistant</h2>

        <div className="chat-history" aria-label="Conversation">
          {messages.map((item, index) => (
            <p key={index} className={`chat-message ${item.role}`}>
              <strong>
                {item.role === "patient" ? "You" : "Assistant"}:
              </strong>{" "}
              {item.content}
            </p>
          ))}
        </div>

        <form onSubmit={(event) => void sendMessage(event)}>
          <label htmlFor="chat-message">Your message</label>
          <textarea
            id="chat-message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="I want to book an eye exam"
            rows={3}
            maxLength={2000}
          />

          <button
            type="submit"
            disabled={busy || !token.trim() || !message.trim()}
          >
            Send message
          </button>
        </form>
      </section>

      {proposal && (
        <section className="panel">
          <h2>Proposed action</h2>

          <p>
            The agent proposed a{" "}
            {proposal.action === "book" ? "booking" : "cancellation"}.
            The backend must verify it before approval.
          </p>

          <button
            type="button"
            onClick={() => void prepareAction()}
            disabled={busy}
          >
            Validate proposal
          </button>
        </section>
      )}

      {prepared && (
        <section className="panel">
          <h2>Review confirmed details</h2>

          <p>
            <strong>Action:</strong>{" "}
            {prepared.action === "book" ? "Book appointment" : "Cancel appointment"}
          </p>

          <dl className="confirmation-details">
            {Object.entries(prepared.details).map(([key, value]) => (
              <div key={key}>
                <dt>{key.replaceAll("_", " ")}</dt>
                <dd>{String(value)}</dd>
              </div>
            ))}
          </dl>

          {prepared.action === "book" && (
            <p className="hint">
              Review the appointment date, provider, service, and price.
              Approval expires after {prepared.expires_in_seconds} seconds.
            </p>
          )}

          {!approved ? (
            <button
              type="button"
              onClick={() => void approveAction()}
              disabled={busy}
            >
              Approve exact details
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void executeAction()}
              disabled={busy}
            >
              {prepared.action === "book"
                ? "Confirm booking"
                : "Confirm cancellation"}
            </button>
          )}

          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => {
              setPrepared(null);
              setApproved(false);
            }}
          >
            Dismiss
          </button>
        </section>
      )}

      {error && <p role="alert" className="error">{error}</p>}
      {result && <p role="status" className="success">{result}</p>}
    </main>
  );
}

export default App;