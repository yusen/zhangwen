import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { BoardProfile } from "@zhangwen/contracts";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BoardProfileLibrary } from "../components/hardware/BoardProfileLibrary";
import { SettingsDialog } from "../components/settings/SettingsDialog";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("K10 BoardProfile Markdown 编辑器", () => {
  it("普通模式不显示或请求档案，专业模式才开放编辑器", async () => {
    const initial = profile();
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/hardware/skills")) return json({ skills: [] });
      if (url.endsWith("/api/hardware/board-profiles")) {
        const { content: _content, ...summary } = initial;
        return json({ profiles: [summary] });
      }
      if (url.endsWith("/api/hardware/board-profiles/k10")) {
        return json({ profile: initial });
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    const regular = renderSettings(false);
    fireEvent.click(screen.getByRole("button", { name: "公共知识" }));
    expect(screen.queryByRole("tab", { name: "开发板档案" })).not.toBeInTheDocument();
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([target]) => String(target).endsWith("/api/hardware/skills")))
        .toBe(true),
    );
    expect(fetchMock.mock.calls.some(([target]) => String(target).includes("/board-profiles")))
      .toBe(false);
    regular.unmount();

    renderSettings(true);
    fireEvent.click(screen.getByRole("button", { name: "公共知识" }));
    fireEvent.click(screen.getByRole("tab", { name: "开发板档案" }));
    expect(await screen.findByRole("textbox", { name: "编辑 K10 BoardProfile" }))
      .toBeInTheDocument();
  });

  it("加载 K10 档案并以 expectedRevision 保存覆盖", async () => {
    const initial = profile();
    const saved = profile({
      content: `${initial.content}\n# 用户覆盖\n`,
      overridden: true,
      revision: "revision-2",
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/hardware/board-profiles") && method === "GET") {
        const { content: _content, ...summary } = initial;
        return json({ profiles: [summary] });
      }
      if (url.endsWith("/api/hardware/board-profiles/k10") && method === "GET") {
        return json({ profile: initial });
      }
      if (url.endsWith("/api/hardware/board-profiles/k10") && method === "PUT") {
        return json({ profile: saved });
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<BoardProfileLibrary />);

    const editor = await screen.findByRole("textbox", { name: "编辑 K10 BoardProfile" });
    expect(screen.getByRole("region", { name: "已绑定 K10 Skill" })).toHaveTextContent(
      "unihiker-k10-micropython-engineer",
    );
    expect(screen.getByRole("region", { name: "已绑定 K10 Skill" })).toHaveTextContent(
      "11 个参考 · 22 个模板 · 3 个示例",
    );
    expect(screen.getByRole("region", { name: "已绑定 K10 Skill" })).toHaveTextContent(
      "语法已验证 · 尚未上板验证",
    );
    fireEvent.change(editor, { target: { value: saved.content } });
    fireEvent.click(screen.getByRole("button", { name: "保存档案" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "已保存 BoardProfile，下一次匹配该开发板时生效。",
    );
    const saveCall = fetchMock.mock.calls.find(
      ([target, init]) =>
        String(target).endsWith("/board-profiles/k10") && init?.method === "PUT",
    );
    expect(JSON.parse(String(saveCall?.[1]?.body))).toEqual({
      content: saved.content,
      expectedRevision: "revision-1",
    });
    expect(screen.getByText("自定义覆盖")).toBeInTheDocument();
  });

  it("revision 冲突时保留未保存 Markdown", async () => {
    const fetchMock = boardProfileFetch({
      saveResponse: () =>
        json(
          { detail: { code: "BOARD_PROFILE_CONFLICT", message: "档案已被更新。" } },
          409,
        ),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<BoardProfileLibrary />);

    const editor = await screen.findByRole("textbox", { name: "编辑 K10 BoardProfile" });
    fireEvent.change(editor, { target: { value: "# 保留我的 K10 修改\n" } });
    fireEvent.click(screen.getByRole("button", { name: "保存档案" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("档案已被更新");
    expect(screen.getByRole("textbox", { name: "编辑 K10 BoardProfile" })).toHaveValue(
      "# 保留我的 K10 修改\n",
    );
  });

  it("确认后恢复内置档案", async () => {
    const overridden = profile({ overridden: true, revision: "revision-custom" });
    const restored = profile({ overridden: false, revision: "revision-restored" });
    const fetchMock = boardProfileFetch({
      initial: overridden,
      resetResponse: () => json({ profile: restored }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<BoardProfileLibrary />);

    await screen.findByRole("textbox", { name: "编辑 K10 BoardProfile" });
    fireEvent.click(screen.getByRole("button", { name: "恢复默认" }));
    fireEvent.click(screen.getByRole("button", { name: "确认恢复" }));

    expect(await screen.findByRole("status")).toHaveTextContent("已恢复内置 BoardProfile。");
    await waitFor(() => expect(screen.getByText("内置默认")).toBeInTheDocument());
    const resetCall = fetchMock.mock.calls.find(([target]) =>
      String(target).endsWith("/board-profiles/k10/reset"),
    );
    expect(JSON.parse(String(resetCall?.[1]?.body))).toEqual({
      expectedRevision: "revision-custom",
    });
  });
});

function boardProfileFetch({
  initial = profile(),
  saveResponse,
  resetResponse,
}: {
  initial?: BoardProfile;
  saveResponse?: () => Response;
  resetResponse?: () => Response;
} = {}) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.endsWith("/api/hardware/board-profiles") && method === "GET") {
      const { content: _content, ...summary } = initial;
      return json({ profiles: [summary] });
    }
    if (url.endsWith("/api/hardware/board-profiles/k10") && method === "GET") {
      return json({ profile: initial });
    }
    if (url.endsWith("/api/hardware/board-profiles/k10") && method === "PUT") {
      return saveResponse?.() ?? json({ profile: initial });
    }
    if (url.endsWith("/api/hardware/board-profiles/k10/reset") && method === "POST") {
      return resetResponse?.() ?? json({ profile: profile() });
    }
    return json({}, 404);
  });
}

function renderSettings(professionalMode: boolean) {
  return render(
    <SettingsDialog
      config={null}
      models={[]}
      saving={false}
      testing={false}
      message={null}
      error={null}
      professionalMode={professionalMode}
      onProfessionalModeChange={vi.fn()}
      onSave={vi.fn(async () => undefined)}
      onClearKey={vi.fn(async () => undefined)}
      onTest={vi.fn(async () => ({
        ok: true,
        message: "ok",
        provider: "deepseek" as const,
        model: "deepseek-v4-flash" as const,
        latencyMs: 1,
      }))}
      onClose={vi.fn()}
    />,
  );
}

function profile(overrides: Partial<BoardProfile> = {}): BoardProfile {
  return {
    id: "k10",
    displayName: "K10",
    aliases: ["K10", "ESP32-S3 K10"],
    platform: "ESP32-S3",
    language: "micropython",
    overridden: false,
    revision: "revision-1",
    skillPackage: {
      id: "unihiker-k10-micropython-engineer",
      name: "unihiker-k10-micropython-engineer",
      version: "1.0.0",
      profileId: "unihiker-k10",
      target: "UNIHIKER K10 / DFR0992",
      runtime: "MicroPython",
      referenceCount: 11,
      templateCount: 22,
      exampleCount: 3,
      syntaxValidated: true,
      hardwareValidated: false,
      revision: "skill-revision-1",
    },
    content: "# K10 BoardProfile\n\n- 使用 MicroPython。\n",
    ...overrides,
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
