import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  HardwareComponent,
  HardwareMediaAsset,
  HardwareSkillDetail,
} from "@zhangwen/contracts";
import { HardwareLibrary } from "../components/hardware/HardwareLibrary";
import { HardwareSelectionDialog } from "../components/hardware/HardwareSelectionDialog";
import { clearAuthSessionToken, setAuthSessionToken } from "../services/api";

const cover: HardwareMediaAsset = {
  path: "assets/cover.webp",
  role: "cover",
  alt: "行空板 K10 正面产品图",
  contentType: "image/webp",
  sha256: "a".repeat(64),
  sourceUrl: "https://www.dfrobot.com/product-2904.html",
  attribution: "DFRobot",
  license: "用于产品识别；公开再分发前确认授权。",
  url: "/api/hardware/skills/k10/media/cover.webp",
};

describe("硬件库真实图片", () => {
  beforeEach(() => {
    setAuthSessionToken("hardware-media-test-token");
    Object.defineProperty(globalThis.URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:hardware-cover"),
    });
    Object.defineProperty(globalThis.URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
  });

  afterEach(() => {
    clearAuthSessionToken();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("知识库通过认证请求加载封面并保留来源说明", async () => {
    const detail = skillFixture();
    const fetchMock = mediaFetch((url) => {
      if (url.endsWith("/api/hardware/skills")) {
        const { files: _files, specification: _spec, rules: _rules, ...summary } = detail;
        return json({ skills: [summary] });
      }
      if (url.endsWith("/api/hardware/skills/k10")) return json({ skill: detail });
      return null;
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<HardwareLibrary />);

    fireEvent.click(await screen.findByRole("button", { name: `查看 ${detail.displayName}` }));
    const image = await screen.findByRole("img", { name: cover.alt });
    expect(image).toHaveAttribute("src", "blob:hardware-cover");
    expect(screen.getByText("图片来源：DFRobot")).toBeInTheDocument();
    expect(screen.getByText("3.3V / 5V")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(cover.url),
      expect.objectContaining({
        headers: expect.objectContaining({}),
      }),
    );
    const mediaCall = fetchMock.mock.calls.find(([input]) =>
      String(input).endsWith(cover.url),
    );
    expect(new Headers(mediaCall?.[1]?.headers).get("Authorization"))
      .toBe("Bearer hardware-media-test-token");
  });

  it("项目硬件选择器显示同一封面，图片失败仍保留器件名称", async () => {
    const component = componentFixture();
    vi.stubGlobal("fetch", mediaFetch((url) => {
      if (url.endsWith("/api/hardware")) return json({ components: [component] });
      return null;
    }));

    render(
      <HardwareSelectionDialog
        open
        initialSelectedIds={[]}
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(await screen.findByRole("img", { name: cover.alt })).toBeInTheDocument();
    expect(screen.getByText("行空板 K10")).toBeInTheDocument();
    expect(screen.getByText("外设 3.3V / 5V")).toBeInTheDocument();
  });
});

function mediaFetch(
  route: (url: string) => Response | null,
) {
  return vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith(cover.url)) {
      return new Response(new Uint8Array([82, 73, 70, 70]), {
        status: 200,
        headers: { "Content-Type": "image/webp" },
      });
    }
    return route(url) ?? json({}, 404);
  });
}

function componentFixture(): HardwareComponent {
  return {
    id: "hw_seed_unihiker_k10",
    name: "行空板 K10",
    category: "MCU",
    status: "ACTIVE",
    electrical: {
      voltage: 5,
      voltageMin: 5,
      voltageMax: 5,
      supplyVoltages: [3.3, 5],
      logicLevel: 3.3,
      peakCurrent: 0,
      communicationProtocol: "GPIO/I2C",
      i2cAddress: null,
      supportedMCUs: ["unihiker-k10"],
      driverName: "unihiker_k10",
      firmwareRequirement: "K10 MicroPython",
    },
    stock: 0,
    price: 0,
    ageRecommendation: 8,
    safetyTags: ["3.3V逻辑"],
    notes: "内置屏幕、摄像头和传感器。",
    createdAt: "2026-07-15T00:00:00Z",
    updatedAt: "2026-07-15T00:00:00Z",
    media: [cover],
  };
}

function skillFixture(): HardwareSkillDetail {
  const component = componentFixture();
  return {
    skillName: "k10",
    componentId: component.id,
    displayName: component.name,
    description: component.notes,
    category: component.category,
    status: "ACTIVE",
    sourceKind: "MIGRATED",
    revision: "a".repeat(24),
    verificationStatus: "OFFICIAL_SOURCE",
    updatedAt: component.updatedAt,
    diagnostics: [],
    media: [cover],
    files: [],
    specification: {
      schema: "zhangwen.hardware-skill/v1",
      componentId: component.id,
      name: component.name,
      category: component.category,
      electrical: component.electrical,
      stock: 0,
      price: 0,
      ageRecommendation: 8,
      safetyTags: component.safetyTags,
      notes: component.notes,
      verificationStatus: "OFFICIAL_SOURCE",
      sourceIds: ["official:dfrobot:dfr0992-en"],
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
