import { useEffect, useState } from "react";
import type { HealthResponse } from "@zhangwen/contracts";
import { apiGet } from "../services/api";

export interface HealthState {
  status: "checking" | "ok" | "recovering" | "disconnected";
  version?: string;
  llmTestMode: "standard" | "fake" | "paid";
  usesPaidLlm: boolean;
}

const POLL_INTERVAL_MS = 5000;
const HEALTH_TIMEOUT_MS = 4000;

export function useHealthCheck(): HealthState {
  const [state, setState] = useState<HealthState>({
    status: "checking",
    llmTestMode: "standard",
    usesPaidLlm: false,
  });

  useEffect(() => {
    let disposed = false;
    let inFlight = false;
    let activeController: AbortController | null = null;
    let consecutiveFailures = 0;

    const recordFailure = () => {
      consecutiveFailures += 1;
      setState((current) => ({
        ...current,
        status: consecutiveFailures >= 3 ? "disconnected" : "recovering",
      }));
    };

    const check = async () => {
      if (disposed || inFlight) return;
      inFlight = true;
      const controller = new AbortController();
      activeController = controller;
      try {
        const data = await apiGet<HealthResponse>(
          "/api/health",
          controller.signal,
          HEALTH_TIMEOUT_MS
        );
        if (disposed) return;
        if (data.status !== "ok") {
          recordFailure();
        } else {
          consecutiveFailures = 0;
          setState({
            status: "ok",
            version: data.version,
            llmTestMode: data.llmTestMode ?? "standard",
            usesPaidLlm: data.usesPaidLlm ?? false,
          });
        }
      } catch {
        if (disposed) return;
        recordFailure();
      } finally {
        if (activeController === controller) activeController = null;
        inFlight = false;
      }
    };

    void check();
    const id = setInterval(() => void check(), POLL_INTERVAL_MS);
    return () => {
      disposed = true;
      clearInterval(id);
      activeController?.abort();
    };
  }, []);

  return state;
}
