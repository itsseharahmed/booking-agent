
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App", () => {
  it("displays the application heading", () => {
    // Arrange: render the React component.
    render(<App />);

    // Assert: patients should see the application title.
    expect(
      screen.getByRole("heading", {
        name: /optometry booking/i,
      })
    ).toBeInTheDocument();
  });

  it("displays the development status", () => {
    render(<App />);

     //screen.debug();
    // The booking feature does not exist yet.
    // We should not display a misleading booking form.
    expect(
      screen.getByText(/booking features coming soon/i)
    ).toBeInTheDocument();
  });
});
