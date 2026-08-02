import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useHealthCheck } from "../hooks/useHealthCheck";

const { apiGetMock } = vi.hoisted(() => ({
  apiGetMock: vi.fn(),
}));

vi.mock("../services/api", () => ({
  apiGet: apiGetMock,
}));

function HealthHarness() {
  const health = useHealthCheck();
  return <span>{health.status}</span>;
}

describe("useHealthCheck", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    apiGetMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("deduplicates slow polls, uses a short timeout, and aborts on unmount", async () => {
    let resolveFirst!: (value: {
      status: "ok";
      version: string;
      llmTestMode: "standard";
      usesPaidLlm: boolean;
    }) => void;
    const first = new Promise<{
      status: "ok";
      version: string;
      llmTestMode: "standard";
      usesPaidLlm: boolean;
    }>((resolve) => {
      resolveFirst = resolve;
    });
    const second = new Promise(() => undefined);
    apiGetMock.mockReturnValueOnce(first).mockReturnValueOnce(second);

    const view = render(<HealthHarness />);

    expect(apiGetMock).toHaveBeenCalledTimes(1);
    const initialCall = apiGetMock.mock.calls.at(0);
    if (!initialCall) throw new Error("initial health request was not recorded");
    expect(initialCall[2]).toBe(4_000);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15_000);
    });
    expect(apiGetMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveFirst({
        status: "ok",
        version: "0.1.0",
        llmTestMode: "standard",
        usesPaidLlm: false,
      });
      await Promise.resolve();
    });
    expect(screen.getByText("ok")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(apiGetMock).toHaveBeenCalledTimes(2);
    const secondCall = apiGetMock.mock.calls.at(1);
    if (!secondCall) throw new Error("second health request was not recorded");
    const activeSignal = secondCall[1] as AbortSignal;
    expect(activeSignal.aborted).toBe(false);

    view.unmount();
    expect(activeSignal.aborted).toBe(true);
  });

  it("treats transient failures as recovery and disconnects after three failures", async () => {
    apiGetMock.mockRejectedValue(new Error("temporary connection failure"));

    render(<HealthHarness />);
    await act(async () => Promise.resolve());
    expect(screen.getByText("recovering")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(screen.getByText("recovering")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(screen.getByText("disconnected")).toBeInTheDocument();
  });

  it("returns to healthy and resets the failure counter", async () => {
    apiGetMock
      .mockRejectedValueOnce(new Error("temporary connection failure"))
      .mockResolvedValue({
        status: "ok",
        version: "0.1.0",
        llmTestMode: "standard",
        usesPaidLlm: false,
      });

    render(<HealthHarness />);
    await act(async () => Promise.resolve());
    expect(screen.getByText("recovering")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_000);
    });
    expect(screen.getByText("ok")).toBeInTheDocument();
  });
});
