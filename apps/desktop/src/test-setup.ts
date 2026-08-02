import "@testing-library/jest-dom/vitest";

Object.defineProperty(document, "queryCommandSupported", {
  configurable: true,
  value: () => false,
});

Object.defineProperty(window, "__TAURI_INTERNALS__", {
  configurable: true,
  value: { test: true },
});
