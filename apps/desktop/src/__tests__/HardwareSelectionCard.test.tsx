import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  ConversationResponseType,
  type ConversationResponse,
} from "@zhangwen/contracts";
import { ConversationResponseCard } from "../components/chat/ConversationResponseCard";

describe("项目缺件提醒卡", () => {
  it("显示缺少能力并通过本地动作打开项目硬件选择器", () => {
    const onOpenHardwareSelection = vi.fn();
    const payload: ConversationResponse = {
      type: ConversationResponseType.HARDWARE_SELECTION,
      summary: "当前项目还缺少两个能力，请补充器件后继续规划。",
      missingCapabilities: ["环境光检测", "声音提醒"],
    };

    render(
      <ConversationResponseCard
        messageId="msg_hardware_gap"
        payload={payload}
        onClarificationDraftChange={vi.fn()}
        onSubmitClarification={vi.fn()}
        onAction={vi.fn()}
        onOpenHardwareSelection={onOpenHardwareSelection}
      />,
    );

    expect(screen.getByText("环境光检测")).toBeInTheDocument();
    expect(screen.getByText("声音提醒")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "选择并添加电子器件" }),
    );
    expect(onOpenHardwareSelection).toHaveBeenCalledTimes(1);
  });
});
