import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AgentPackageEditor } from "../components/floating/AgentPackageEditor";
import { HardwareSkillEditor } from "../components/floating/HardwareSkillEditor";
import { HARDWARE_SKILL_UPDATED_EVENT } from "../utils/hardwareSkillEvents";

vi.mock("../components/floating/MonacoCodeEditor", () => ({
  default: ({
    filePath,
    value,
    onChange,
    readOnly,
  }: {
    filePath: string;
    value: string;
    onChange: (value: string) => void;
    readOnly?: boolean;
  }) => (
    <textarea
      aria-label={`编辑 ${filePath}`}
      value={value}
      readOnly={readOnly}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Skill 项目编辑器", () => {
  it("Hardware Skill 保留多文件草稿并按同一 revision 原子保存", async () => {
    let detail = hardwareSkillFixture("skill-revision-1");
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT") {
        const body = JSON.parse(String(init.body ?? "{}"));
        detail = {
          ...detail,
          revision: "skill-revision-2",
          files: detail.files.map((file) =>
            body.updates.find((update: { path: string }) => update.path === file.path)
              ? {
                  ...file,
                  content: body.updates.find(
                    (update: { path: string; content: string }) =>
                      update.path === file.path,
                  ).content,
                }
              : file,
          ),
        };
        return json({ skill: detail });
      }
      return json({ skill: detail });
    });
    vi.stubGlobal("fetch", fetchMock);
    const onDirtyChange = vi.fn();
    const updatedEvent = vi.fn();
    window.addEventListener(HARDWARE_SKILL_UPDATED_EVENT, updatedEvent);

    render(
      <HardwareSkillEditor
        skillName="bme280-environment-sensor"
        onDirtyChange={onDirtyChange}
      />,
    );

    const editor = await screen.findByRole("region", {
      name: "BME280 环境传感器 Hardware Skill 项目编辑器",
    });
    expect(within(editor).getByText("manifest.json（系统只读）")).toBeInTheDocument();
    expect(within(editor).getByText("PY")).toBeInTheDocument();
    fireEvent.change(within(editor).getByRole("textbox", { name: "编辑 SKILL.md" }), {
      target: { value: "# BME280\n\n新的入口说明" },
    });
    fireEvent.click(within(editor).getByRole("button", { name: /规格参数/ }));
    fireEvent.change(
      within(editor).getByRole("textbox", { name: "编辑 references/specifications.md" }),
      { target: { value: "```json\n{\"voltage\": 3.3}\n```" } },
    );

    expect(within(editor).getByText("2 个文件有未保存修改")).toBeInTheDocument();
    fireEvent.click(within(editor).getByRole("button", { name: "保存全部" }));

    expect(await within(editor).findByText("已保存 2 个文件。下一次工程师回复将读取新版本。"))
      .toBeInTheDocument();
    const requests = fetchMock.mock.calls
      .filter(([, init]) => init?.method === "PUT")
    expect(requests).toHaveLength(1);
    expect(String(requests[0]?.[0])).toContain("/files/batch");
    const body = JSON.parse(String(requests[0]?.[1]?.body ?? "{}"));
    expect(body).toMatchObject({ expectedRevision: "skill-revision-1" });
    expect(body.updates).toHaveLength(2);
    expect(updatedEvent).toHaveBeenCalledTimes(1);
    expect(onDirtyChange).toHaveBeenLastCalledWith(false);
    window.removeEventListener(HARDWARE_SKILL_UPDATED_EVENT, updatedEvent);
  });

  it("Agent Package 遇到 409 刷新 revision 但保留当前 Markdown 草稿", async () => {
    let revision = "agent-revision-1";
    let putCount = 0;
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT") {
        putCount += 1;
        if (putCount === 1) {
          revision = "agent-revision-2";
          return json({
            detail: {
              code: "AGENT_PACKAGE_CONFLICT",
              message: "行为项目已更新。",
            },
          }, 409);
        }
        const body = JSON.parse(String(init.body ?? "{}"));
        revision = "agent-revision-3";
        return json({ package: agentPackageFixture(revision, body.content) });
      }
      return json({ package: agentPackageFixture(revision) });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AgentPackageEditor expertType="problem_guide" />);

    const editor = await screen.findByRole("region", {
      name: "问题引导师行为项目编辑器",
    });
    const input = within(editor).getByRole("textbox", { name: "编辑 SKILL.md" });
    fireEvent.change(input, { target: { value: "# 问题引导师\n\n保留我的修改" } });
    fireEvent.click(within(editor).getByRole("button", { name: "保存全部" }));

    expect(await within(editor).findByRole("alert")).toHaveTextContent(
      "服务端版本已更新，当前草稿仍保留",
    );
    expect(input).toHaveValue("# 问题引导师\n\n保留我的修改");
    fireEvent.click(within(editor).getByRole("button", { name: "保存全部" }));
    await waitFor(() => expect(putCount).toBe(2));
    const secondBody = JSON.parse(String(
      fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT")[1]?.[1]?.body ?? "{}",
    ));
    expect(secondBody).toMatchObject({ expectedRevision: "agent-revision-2" });
  });

  it("Agent Package 二次确认后恢复选中文件的内置默认", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/files/reset") && init?.method === "POST") {
        return json({
          package: agentPackageFixture("agent-revision-2", "# 问题引导师", false),
        });
      }
      return json({
        package: agentPackageFixture(
          "agent-revision-1",
          "# 问题引导师\n\n用户覆盖",
          true,
        ),
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<AgentPackageEditor expertType="problem_guide" />);

    const editor = await screen.findByRole("region", {
      name: "问题引导师行为项目编辑器",
    });
    fireEvent.click(within(editor).getByRole("button", { name: "恢复内置" }));

    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining("恢复为内置默认内容"));
    expect(await within(editor).findByText(/已把 SKILL.md 恢复为内置默认内容/))
      .toBeInTheDocument();
    const resetBody = JSON.parse(String(
      fetchMock.mock.calls.find(([target]) => String(target).endsWith("/files/reset"))?.[1]?.body ?? "{}",
    ));
    expect(resetBody).toEqual({
      path: "SKILL.md",
      expectedRevision: "agent-revision-1",
    });
  });
});

function hardwareSkillFixture(revision: string) {
  return {
    skillName: "bme280-environment-sensor",
    componentId: "hw_bme280",
    displayName: "BME280 环境传感器",
    description: "I2C 环境传感器",
    category: "SENSOR",
    status: "ACTIVE",
    sourceKind: "MIGRATED",
    revision,
    verificationStatus: "VERIFIED",
    updatedAt: "2026-07-15T00:00:00Z",
    diagnostics: [],
    files: [
      { path: "SKILL.md", title: "入口说明", kind: "entry", content: "# BME280", editable: true },
      { path: "references/specifications.md", title: "规格参数", kind: "reference", content: "{}", editable: true },
      { path: "references/compatibility-rules.md", title: "兼容规则", kind: "reference", content: "[]", editable: true },
      { path: "references/mechanical.md", title: "结构与机械档案", kind: "reference", content: "# 结构", editable: true },
      { path: "models/cadquery.py", title: "CadQuery 参考模型", kind: "model", content: "result = None\n", editable: true },
      { path: "examples/usage.md", title: "使用示例", kind: "example", content: "# 示例", editable: true },
    ],
    specification: {
      schema: "zhangwen.hardware-skill/v1",
      componentId: "hw_bme280",
      name: "BME280 环境传感器",
      category: "SENSOR",
      electrical: {
        voltage: 3.3,
        logicLevel: 3.3,
        peakCurrent: 0.001,
        communicationProtocol: "I2C",
        i2cAddress: "0x76",
        supportedMCUs: ["ESP32"],
        driverName: "bme280",
        firmwareRequirement: "MicroPython",
      },
      stock: 0,
      price: 0,
      ageRecommendation: null,
      safetyTags: ["低压"],
      notes: "",
      verificationStatus: "VERIFIED",
      sourceIds: [],
    },
    rules: [],
  };
}

function agentPackageFixture(
  revision: string,
  entry = "# 问题引导师",
  overridden = false,
) {
  return {
    expertType: "problem_guide",
    skillName: "problem-guide",
    displayName: "问题引导师",
    description: "澄清目标和约束。",
    icon: "spark",
    entryFile: "SKILL.md",
    skillIds: ["hardware-selection"],
    supportedArtifactTypes: ["requirements"],
    capabilityBoundaries: ["不操作设备"],
    fileCount: 2,
    overridden,
    revision,
    validationIssues: [],
    files: [
      { path: "SKILL.md", title: "主 SKILL.md", kind: "entry", content: entry, editable: true, overridden },
      { path: "references/clarification.md", title: "澄清规则", kind: "reference", content: "# 澄清", editable: true, overridden: false },
    ],
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
