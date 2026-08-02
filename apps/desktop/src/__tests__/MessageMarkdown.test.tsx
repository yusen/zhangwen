import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MessageMarkdown } from "../components/chat/MessageMarkdown";

describe("对话 Markdown 与历史代码导入", () => {
  it("按结构渲染标题、列表和 Python 代码，不执行原始 HTML", () => {
    render(
      <MessageMarkdown
        messageId="message_1"
        content={[
          "## 方案",
          "",
          "- 使用 MicroPython",
          "- 保存为 main.py",
          "",
          "```python",
          "print('<script>not html</script>')",
          "```",
          "",
          "<img src=x onerror=alert(1)>",
        ].join("\n")}
      />,
    );

    expect(screen.getByRole("heading", { name: "方案" })).toBeInTheDocument();
    expect(screen.getByRole("list")).toHaveTextContent("使用 MicroPython");
    expect(screen.getByRole("region", { name: "Python 代码" })).toHaveTextContent(
      "print('<script>not html</script>')",
    );
    expect(document.querySelector("img")).toBeNull();
  });

  it("只在用户明确点击后按持久化消息 ID 导入", async () => {
    const onImport = vi.fn(async () => undefined);
    render(
      <MessageMarkdown
        messageId="message_saved_1"
        content={"```micropython\nprint('K10')\n```"}
        onImportPython={onImport}
      />,
    );

    expect(onImport).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "保存到产物" }));
    await waitFor(() => expect(onImport).toHaveBeenCalledWith("message_saved_1"));
  });
});
