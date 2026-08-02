import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HealthIndicator } from "../components/health/HealthIndicator";

describe("HealthIndicator", () => {
  it.each([
    ["checking", "本地服务连接中", "连接中", "health-checking"],
    ["ok", "本地服务正常", "正常", "health-connected"],
    ["recovering", "本地服务正在恢复连接", "恢复中", "health-recovering"],
    ["disconnected", "本地服务未连接", "未连接", "health-disconnected"],
  ] as const)("renders %s state without ambiguity", (status, label, compactLabel, className) => {
    render(<HealthIndicator status={status} />);

    const indicator = screen.getByTestId("health-indicator");
    expect(indicator).toHaveTextContent(label);
    expect(within(indicator).getByText(compactLabel)).toHaveClass("health-label-compact");
    expect(indicator).toHaveAccessibleName(label);
    expect(indicator).toHaveClass(className);
  });

  it("does not expose internal LLM billing mode in the top bar", () => {
    render(<HealthIndicator status="ok" />);

    expect(screen.queryByTestId("llm-test-mode")).not.toBeInTheDocument();
    expect(screen.queryByText(/免费测试|付费测试/)).not.toBeInTheDocument();
  });
});
