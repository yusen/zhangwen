import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { HardwareSkillDetail, HardwareSkillSummary } from "@zhangwen/contracts";
import { HardwareLibrary } from "../components/hardware/HardwareLibrary";
import { publishHardwareSkillUpdated } from "../utils/hardwareSkillEvents";

describe("Hardware Skill 硬件库", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("从新 API 展示 Skill 列表、结构化参数和三师共享状态", async () => {
    const detail = hardwareSkillFixture();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/hardware/skills")) return json({ skills: [summary(detail)] });
      if (url.endsWith("/api/hardware/skills/dht22-sensor")) return json({ skill: detail });
      return json({}, 404);
    }));

    render(<HardwareLibrary />);

    const selectSkill = await screen.findByRole(
      "button",
      { name: "查看 DHT22 温湿度传感器" },
      { timeout: 5_000 },
    );
    expect(screen.queryByText("0x40")).not.toBeInTheDocument();
    fireEvent.click(selectSkill);
    const detailRegion = await screen.findByRole("region", {
      name: "硬件知识 详情 DHT22 温湿度传感器",
    });
    expect(within(detailRegion).getByText("0x40")).toBeInTheDocument();
    expect(within(detailRegion).getByText(/三位工程师共享同一有效版本/)).toBeInTheDocument();
    expect(within(detailRegion).queryByText("dht22-sensor")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("搜索硬件知识"), {
      target: { value: "不存在" },
    });
    expect(screen.getByText("没有匹配的硬件知识项目。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "新建硬件知识" })).toBeInTheDocument();
    expect(screen.queryByText("Hardware Skill 硬件库")).not.toBeInTheDocument();
  });

  it("专业模式从详情打开目录化 Skill 项目，而不是在设置内展开编辑器", async () => {
    const detail = hardwareSkillFixture();
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/hardware/skills")) return json({ skills: [summary(detail)] });
      return json({ skill: detail });
    }));
    const onOpenSkillProject = vi.fn();

    render(
      <HardwareLibrary
        professionalMode
        onOpenSkillProject={onOpenSkillProject}
      />,
    );

    fireEvent.click(await screen.findByRole("button", {
      name: "查看 DHT22 温湿度传感器",
    }));
    const open = await screen.findByRole("button", {
      name: "打开 Skill 项目 DHT22 温湿度传感器",
    });
    fireEvent.click(open);
    expect(onOpenSkillProject).toHaveBeenCalledWith(summary(detail));
    expect(screen.queryByLabelText(/Hardware Skill 项目编辑器/)).not.toBeInTheDocument();
    expect(screen.getByText("references/specifications.md")).toBeInTheDocument();
  });

  it("Skill 保存后保持当前目录，用户手动刷新才切换快照", async () => {
    const detail = hardwareSkillFixture();
    const updated = {
      ...detail,
      revision: "skill-revision-2",
      description: "刚保存的新资料",
      specification: {
        ...detail.specification,
        electrical: {
          ...detail.specification.electrical,
          voltage: 5,
        },
      },
    } satisfies HardwareSkillDetail;
    let refreshed = false;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/hardware/catalog/refresh") && init?.method === "POST") {
        refreshed = true;
        return json({ skills: [summary(updated)], refreshedAt: "2026-07-19T00:00:00Z" });
      }
      if (url.endsWith("/api/hardware/skills")) return json({ skills: [summary(detail)] });
      return json({ skill: refreshed ? updated : detail });
    }));

    render(<HardwareLibrary professionalMode />);
    fireEvent.click(await screen.findByRole("button", {
      name: "查看 DHT22 温湿度传感器",
    }));
    const region = await screen.findByRole("region", {
      name: "Hardware Skill 详情 DHT22 温湿度传感器",
    });
    expect(within(region).getByText("3.3V")).toBeInTheDocument();
    expect(within(region).getByText("3.3 V")).toBeInTheDocument();

    act(() => {
      publishHardwareSkillUpdated(updated);
    });

    expect(screen.getByText(/请手动刷新硬件目录/)).toBeInTheDocument();
    expect(within(region).getByText("3.3V")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "刷新硬件目录（有更新）" }));
    expect(await within(region).findByText("5V")).toBeInTheDocument();
    expect(within(region).getByText("刚保存的新资料")).toBeInTheDocument();
  });
});

function summary(detail: HardwareSkillDetail): HardwareSkillSummary {
  const { files: _files, specification: _specification, rules: _rules, ...result } = detail;
  return result;
}

function hardwareSkillFixture(): HardwareSkillDetail {
  return {
    skillName: "dht22-sensor",
    componentId: "hw_dht22",
    displayName: "DHT22 温湿度传感器",
    description: "适用于低压环境监测",
    category: "SENSOR",
    status: "ACTIVE",
    sourceKind: "MIGRATED",
    revision: "skill-revision-1",
    verificationStatus: "VERIFIED",
    updatedAt: "2026-07-15T00:00:00Z",
    diagnostics: [],
    media: [],
    files: [
      { path: "SKILL.md", title: "入口", kind: "entry", content: "# DHT22", editable: true },
      { path: "references/specifications.md", title: "规格", kind: "reference", content: "{}", editable: true },
      { path: "references/compatibility-rules.md", title: "规则", kind: "reference", content: "[]", editable: true },
    ],
    specification: {
      schema: "zhangwen.hardware-skill/v1",
      componentId: "hw_dht22",
      name: "DHT22 温湿度传感器",
      category: "SENSOR",
      electrical: {
        voltage: 3.3,
        logicLevel: 3.3,
        peakCurrent: 0.02,
        communicationProtocol: "I2C",
        i2cAddress: "0x40",
        supportedMCUs: ["ESP32", "K10"],
        driverName: "dht",
        firmwareRequirement: "MicroPython",
      },
      stock: 8,
      price: 18,
      ageRecommendation: 10,
      safetyTags: ["低压"],
      notes: "外壳需要保留通风孔",
      verificationStatus: "VERIFIED",
      sourceIds: ["legacy-component"],
    },
    rules: [],
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
