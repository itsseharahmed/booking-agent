
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Remove rendered React components after every test.
//
// This ensures each test starts with a clean DOM.
// Without cleanup, components from previous tests
// can remain and cause duplicate-element errors.
afterEach(() => {
  cleanup();
});
