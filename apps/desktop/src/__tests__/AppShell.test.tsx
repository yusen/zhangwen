import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { AppShell } from "../components/layout/AppShell";

// Mock useHealthCheck 避免实际网络请求
vi.mock("../hooks/useHealthCheck", () => ({
  useHealthCheck: () => ({ status: "ok" as const, version: "0.1.0" }),
}));

describe("AppShell 布局不变量", () => {
  beforeEach(() => {
    render(<AppShell />);
  });

  it("左侧项目栏存在", () => {
    expect(screen.getByTestId("left-sidebar")).toBeInTheDocument();
  });

  it("中央主对话区域存在", () => {
    expect(screen.getByTestId("center-chat")).toBeInTheDocument();
  });

  it("右侧栏存在", () => {
    expect(screen.getByTestId("right-panel")).toBeInTheDocument();
  });

  it("一句创意项目创建入口存在", () => {
    fireEvent.click(within(screen.getByRole("banner")).getByRole("button", { name: "新建项目" }));
    const dialog = screen.getByRole("dialog", { name: "新建项目" });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByLabelText("新项目创意")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始项目" })).toBeInTheDocument();
  });

  it("健康指示器存在", () => {
    expect(screen.getByTestId("health-indicator")).toBeInTheDocument();
  });

  it("产品名显示为'掌问'", () => {
    const brand = screen.getByText("掌问", { selector: ".brand-name" });
    expect(brand).toBeInTheDocument();
  });

  it("右侧三个 Tab 同时存在", () => {
    expect(screen.getByRole("tab", { name: "工作" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "产物" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "设备" })).toBeInTheDocument();
  });
});
