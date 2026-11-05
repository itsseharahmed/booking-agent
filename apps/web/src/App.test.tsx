import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("shows the authenticated booking interface", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /optometry booking/i }),
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText(/patient access token/i),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: /send message/i }),
    ).toBeDisabled();
  });

  it("sends authenticated chat requests", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        conversation_id: "test-conversation",
        response: "Which clinic would you prefer?",
        proposal: null,
      }),
    });

    vi.stubGlobal("fetch", mockFetch);

    render(<App />);

    fireEvent.change(screen.getByLabelText(/patient access token/i), {
      target: { value: "patient-test-token" },
    });

    fireEvent.change(screen.getByLabelText(/your message/i), {
      target: { value: "I want an eye exam" },
    });

    fireEvent.click(screen.getByRole("button", { name: /send message/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/which clinic would you prefer/i),
      ).toBeInTheDocument();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      "/agent/chat",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer patient-test-token",
        }),
      }),
    );
  });

  it("cannot approve a proposal without backend validation", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        conversation_id: "test-conversation",
        response: "Please review the cancellation.",
        proposal: {
          action: "cancel",
          appointment_id: 42,
          requires_confirmation: true,
        },
      }),
    });

    vi.stubGlobal("fetch", mockFetch);

    render(<App />);

    fireEvent.change(screen.getByLabelText(/patient access token/i), {
      target: { value: "patient-test-token" },
    });

    fireEvent.change(screen.getByLabelText(/your message/i), {
      target: { value: "Cancel appointment 42" },
    });

    fireEvent.click(screen.getByRole("button", { name: /send message/i }));

    expect(
      await screen.findByRole("button", { name: /validate proposal/i }),
    ).toBeInTheDocument();

    expect(
      screen.queryByRole("button", { name: /confirm cancellation/i }),
    ).not.toBeInTheDocument();
  });
});