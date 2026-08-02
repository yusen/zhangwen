import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HardwareSkillCreator } from "../components/floating/HardwareSkillCreator";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Hardware Skill 创建流程", () => {
  it("通过资料、补充和预览确认创建受控 Hardware Skill", async () => {
    const onCreated = vi.fn();
    let revision = "draft-revision-1";
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/hardware/skills/drafts") && init?.method === "POST") {
        return json({
          draft: draftFixture(revision, false, ["额定工作电压是多少？"]),
        }, 201);
      }
      if (url.endsWith("/api/hardware/skills/drafts/draft_1/messages") && init?.method === "POST") {
        revision = "draft-revision-2";
        return json({ draft: draftFixture(revision, true, []) });
      }
      if (url.endsWith("/api/hardware/skills/drafts/draft_1/confirm") && init?.method === "POST") {
        return json({ skill: hardwareSkillFixture() }, 201);
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<HardwareSkillCreator onCreated={onCreated} onCancel={vi.fn()} />);

    const creator = screen.getByRole("region", { name: "创建 Hardware Skill" });
    fireEvent.change(within(creator).getByLabelText("Skill 名称"), {
      target: { value: "BME280 环境传感器" },
    });
    fireEvent.change(within(creator).getByLabelText("粘贴资料"), {
      target: { value: "BME280 使用 3.3V，I2C 地址为 0x76。" },
    });
    const pdf = new File([Uint8Array.from([0x25, 0x50, 0x44, 0x46])], "bme280.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(pdf, "arrayBuffer", {
      value: async () => Uint8Array.from([0x25, 0x50, 0x44, 0x46]).buffer,
    });
    fireEvent.change(within(creator).getByLabelText("上传 Hardware Skill 资料"), {
      target: { files: [pdf] },
    });
    expect(await within(creator).findByText("bme280.pdf")).toBeInTheDocument();
    fireEvent.click(within(creator).getByRole("button", { name: "生成草稿" }));

    expect(await within(creator).findByText("额定工作电压是多少？")).toBeInTheDocument();
    fireEvent.change(within(creator).getByLabelText("补充说明"), {
      target: { value: "额定工作电压 3.3V，峰值电流 1mA。" },
    });
    fireEvent.click(within(creator).getByRole("button", { name: "提交补充" }));

    expect(await within(creator).findByRole("button", { name: "预览确认" })).toBeEnabled();
    fireEvent.click(within(creator).getByRole("button", { name: "预览确认" }));
    expect(within(creator).getByText("references/specifications.md")).toBeInTheDocument();
    expect(within(creator).getByText("range-overlap")).toBeInTheDocument();
    fireEvent.click(within(creator).getByRole("button", { name: "确认创建" }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(hardwareSkillFixture()));
    const createBody = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body ?? "{}"));
    expect(createBody).toEqual({
      name: "BME280 环境传感器",
      description: undefined,
      sources: [
        {
          name: "pasted-notes.md",
          mediaType: "text/markdown",
          content: "BME280 使用 3.3V，I2C 地址为 0x76。",
        },
        {
          name: "bme280.pdf",
          mediaType: "application/pdf",
          content: "JVBERg==",
        },
      ],
    });
    const messageBody = JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body ?? "{}"));
    expect(messageBody).toEqual({
      message: "额定工作电压 3.3V，峰值电流 1mA。",
      expectedRevision: "draft-revision-1",
    });
  });

  it("普通模式隐藏 Skill 术语", () => {
    render(
      <HardwareSkillCreator
        technicalLabels={false}
        onCreated={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    const creator = screen.getByRole("region", { name: "创建硬件知识" });
    expect(within(creator).getByLabelText("硬件简短说明")).toBeInTheDocument();
    expect(within(creator).getByRole("button", { name: "关闭硬件知识创建器" }))
      .toBeInTheDocument();
    expect(within(creator).queryByLabelText("Skill 简短说明")).not.toBeInTheDocument();
    expect(within(creator).queryByText(/Hardware Skill/)).not.toBeInTheDocument();
  });

  it("逐项显示阻塞诊断并在设置卸载时删除服务端草稿", async () => {
    const diagnostic = {
      path: "references/specifications.md",
      code: "PDF_TEXT_EMPTY",
      message: "PDF 未提取到可用文本；扫描件需要先转换为文本。",
      severity: "error" as const,
    };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/hardware/skills/drafts") && init?.method === "POST") {
        return json({
          draft: {
            ...draftFixture("draft-revision-1", false, []),
            diagnostics: [diagnostic],
          },
        }, 201);
      }
      if (url.endsWith("/api/hardware/skills/drafts/draft_1") && init?.method === "DELETE") {
        return new Response(null, { status: 204 });
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    const rendered = render(
      <StrictMode>
        <HardwareSkillCreator onCreated={vi.fn()} onCancel={vi.fn()} />
      </StrictMode>,
    );
    const creator = screen.getByRole("region", { name: "创建 Hardware Skill" });
    fireEvent.change(within(creator).getByLabelText("粘贴资料"), {
      target: { value: "扫描版数据手册" },
    });
    fireEvent.click(within(creator).getByRole("button", { name: "生成草稿" }));

    expect(await within(creator).findByRole("alert")).toHaveTextContent(
      "PDF 未提取到可用文本",
    );
    expect(within(creator).getByText("references/specifications.md")).toBeInTheDocument();
    expect(within(creator).getByRole("button", { name: "预览确认" })).toBeDisabled();

    rendered.unmount();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/hardware/skills/drafts/draft_1"),
      expect.objectContaining({ method: "DELETE" }),
    ));
  });
});

function draftFixture(revision: string, canConfirm: boolean, missingQuestions: string[]) {
  const skill = hardwareSkillFixture();
  return {
    id: "draft_1",
    status: "DRAFT",
    revision,
    sources: [{ name: "pasted-notes.md", mediaType: "text/markdown" }],
    files: skill.files,
    specification: skill.specification,
    rules: skill.rules,
    missingQuestions,
    diagnostics: [],
    canConfirm,
  };
}

function hardwareSkillFixture() {
  return {
    skillName: "bme280-environment-sensor",
    componentId: "hw_bme280",
    displayName: "BME280 环境传感器",
    description: "I2C 环境传感器",
    category: "SENSOR",
    status: "ACTIVE",
    sourceKind: "UPLOAD",
    revision: "skill-revision-1",
    verificationStatus: "VERIFIED",
    updatedAt: "2026-07-15T00:00:00Z",
    diagnostics: [],
    files: [
      { path: "SKILL.md", title: "入口", kind: "entry", content: "# BME280", editable: true },
      { path: "references/specifications.md", title: "规格", kind: "reference", content: "{}", editable: true },
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
      sourceIds: ["pasted-notes.md"],
    },
    rules: [
      {
        id: "voltage-compatible",
        operator: "range-overlap",
        severity: "FAIL",
        message: "工作电压必须兼容",
        params: {},
      },
    ],
  } as const;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
