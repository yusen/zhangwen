import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  BudgetPreference,
  TechnicalLevel,
  UserPersona,
} from "@zhangwen/contracts";
import { AccountProfileSettings } from "../components/settings/AccountProfileSettings";
import { getAccountProfile, updateAccountProfile } from "../services/authApi";

vi.mock("../services/authApi", () => ({
  getAccountProfile: vi.fn(),
  updateAccountProfile: vi.fn(),
}));

const profile = {
  persona: UserPersona.TEACHER,
  technicalLevel: TechnicalLevel.BEGINNER,
  preferredBoards: ["K10"],
  budgetPreference: BudgetPreference.BALANCED,
  needsLesson: true,
  completed: true,
};

describe("设置中的使用偏好", () => {
  beforeEach(() => {
    vi.mocked(getAccountProfile).mockResolvedValue({
      account: {
        id: "user-1",
        email: "teacher@example.com",
        displayName: "教师",
        emailVerified: true,
        createdAt: "2026-07-25T00:00:00Z",
      },
      profile,
    });
    vi.mocked(updateAccountProfile).mockResolvedValue({
      account: {
        id: "user-1",
        email: "teacher@example.com",
        displayName: "教师",
        emailVerified: true,
        createdAt: "2026-07-25T00:00:00Z",
      },
      profile: { ...profile, preferredBoards: ["K10", "ESP32"] },
    });
  });

  it("读取、修改并保存画像，明确不改变权限和设备安全策略", async () => {
    render(<AccountProfileSettings />);
    expect(await screen.findByDisplayValue("K10")).toBeInTheDocument();
    expect(screen.getByText(/不会改变权限或设备安全规则/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("常用板卡"), {
      target: { value: "K10、ESP32" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存使用偏好" }));

    await waitFor(() => expect(updateAccountProfile).toHaveBeenCalledWith({
      ...profile,
      preferredBoards: ["K10", "ESP32"],
      completed: true,
    }));
    expect(await screen.findByText(/使用偏好已保存/)).toBeInTheDocument();
  });
});
