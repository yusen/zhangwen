import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import {
  HardwareCategory,
  HardwareComponentStatus,
  type HardwareComponent,
  type MechanicalProfileSummary,
} from "@zhangwen/contracts";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MechanicalProfileLibrary } from "../components/hardware/MechanicalProfileLibrary";
import { SettingsDialog } from "../components/settings/SettingsDialog";
import { HARDWARE_SKILL_UPDATED_EVENT } from "../utils/hardwareSkillEvents";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("结构工程师机械档案产品面", () => {
  it("普通模式不挂载或请求机械档案，专业模式点击第三个内部 Tab 后才加载", async () => {
    const fetchMock = mechanicalFetch();
    vi.stubGlobal("fetch", fetchMock);

    const regular = renderSettings(false);
    fireEvent.click(screen.getByRole("button", { name: "公共知识" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByRole("tab", { name: "机械档案" })).not.toBeInTheDocument();
    expect(requests(fetchMock, "/api/hardware/mechanical-profiles")).toHaveLength(0);
    regular.unmount();

    renderSettings(true);
    fireEvent.click(screen.getByRole("button", { name: "公共知识" }));
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "器件知识",
      "开发板档案",
      "机械档案",
    ]);
    expect(requests(fetchMock, "/api/hardware/mechanical-profiles")).toHaveLength(0);

    fireEvent.click(screen.getByRole("tab", { name: "机械档案" }));
    expect(await screen.findByRole("region", { name: "机械档案" })).toBeInTheDocument();
    await waitFor(() =>
      expect(requests(fetchMock, "/api/hardware/mechanical-profiles")).toHaveLength(1),
    );
  });

  it("展示机械证据并用精确 profileId 和 revision 关联，锁定映射不可解除", async () => {
    let profiles = [profile()];
    const fetchMock = mechanicalFetch({
      getProfiles: () => profiles,
      onPut: (hardwareId) => {
        profiles = profiles.map((item) => ({
          ...item,
          confirmedHardwareIds: item.confirmedHardwareIds.includes(hardwareId)
            ? item.confirmedHardwareIds
            : [...item.confirmedHardwareIds, hardwareId],
        }));
      },
      onDelete: (hardwareId) => {
        profiles = profiles.map((item) => ({
          ...item,
          confirmedHardwareIds: item.confirmedHardwareIds.filter((id) => id !== hardwareId),
        }));
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<MechanicalProfileLibrary />);

    const item = await screen.findByRole("article", { name: "XIAO ESP32S3" });
    expect(item).toHaveTextContent("21 x 17.8 x 3.5 mm");
    expect(item).toHaveTextContent("边缘限位");
    expect(item).toHaveTextContent("底壳内底面、上盖内侧");
    expect(item).toHaveTextContent("可信内置档案 · 参数化包络");
    const hash = within(item).getByText("a".repeat(12));
    expect(hash).toHaveAttribute("title", "a".repeat(64));

    const select = within(item).getByRole("combobox", {
      name: "选择关联到 XIAO ESP32S3 的硬件",
    });
    expect(within(select).queryByRole("option", { name: /K10/ })).not.toBeInTheDocument();
    const confirmButton = within(item).getByRole("button", { name: "确认关联" });
    expect(confirmButton).toBeDisabled();
    fireEvent.change(select, { target: { value: "hw-new" } });
    fireEvent.click(confirmButton);

    expect(await screen.findByRole("status")).toHaveTextContent(
      "已将 新按钮 (hw-new) 关联到 XIAO ESP32S3",
    );
    const putCall = fetchMock.mock.calls.find(
      ([target, init]) =>
        String(target).endsWith("/api/hardware/hw-new/mechanical-profile-link") &&
        init?.method === "PUT",
    );
    expect(JSON.parse(String(putCall?.[1]?.body))).toEqual({
      profileId: "xiao_esp32s3",
      revision: "xiao-revision-7",
    });

    const lockedButton = within(item).getByRole("button", {
      name: "解除 K10 (hw-locked) 与 XIAO ESP32S3 的关联",
    });
    expect(lockedButton).toBeDisabled();
    expect(lockedButton).toHaveAttribute("title", "内置映射不可解除");

    const removeButton = within(item).getByRole("button", {
      name: "解除 旧按钮 (hw-free) 与 XIAO ESP32S3 的关联",
    });
    await waitFor(() => expect(removeButton).toBeEnabled());
    fireEvent.click(removeButton);
    expect(await screen.findByRole("status")).toHaveTextContent(
      "已解除 旧按钮 (hw-free) 的机械档案关联",
    );
    expect(
      fetchMock.mock.calls.some(
        ([target, init]) =>
          String(target).endsWith("/api/hardware/hw-free/mechanical-profile-link") &&
          init?.method === "DELETE",
      ),
    ).toBe(true);
  });

  it("先按当前 mechanical.md 自然描述生成，再把新 revision 交给 3D 预览浮窗", async () => {
    const fetchMock = mechanicalFetch();
    const onOpenPreview = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<MechanicalProfileLibrary onOpenPreview={onOpenPreview} />);

    const item = await screen.findByRole("article", { name: "XIAO ESP32S3" });
    fireEvent.click(within(item).getByRole("button", { name: "查看 XIAO ESP32S3 3D 预览" }));

    expect(within(item).getByRole("button", { name: "查看 XIAO ESP32S3 3D 预览" })).toHaveTextContent(
      "生成预览中",
    );
    await waitFor(() => expect(onOpenPreview).toHaveBeenCalledTimes(1));
    expect(onOpenPreview.mock.calls[0]?.[0]).toMatchObject({
      profileId: "xiao_esp32s3",
      revision: "xiao-revision-7",
      modelKind: "envelope",
      mountingHoles: [],
    });
    const previewCall = fetchMock.mock.calls.find(
      ([target, init]) =>
        String(target).endsWith(
          "/api/hardware/mechanical-profiles/xiao_esp32s3/preview",
        ) && init?.method === "POST",
    );
    expect(JSON.parse(String(previewCall?.[1]?.body))).toEqual({
      revision: "xiao-revision-7",
    });
  });

  it("自然描述生成失败时不打开旧预览并显示明确错误", async () => {
    const fetchMock = mechanicalFetch({ previewError: "机械自然描述无法解析" });
    const onOpenPreview = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<MechanicalProfileLibrary onOpenPreview={onOpenPreview} />);

    const item = await screen.findByRole("article", { name: "XIAO ESP32S3" });
    fireEvent.click(within(item).getByRole("button", { name: "查看 XIAO ESP32S3 3D 预览" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("机械自然描述无法解析");
    expect(onOpenPreview).not.toHaveBeenCalled();
  });

  it("加载失败显示明确错误，并可手动刷新恢复", async () => {
    let shouldFail = true;
    const fetchMock = mechanicalFetch({
      getProfiles: () => {
        if (shouldFail) throw new Error("临时失败");
        return [profile()];
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<MechanicalProfileLibrary />);

    expect(await screen.findByRole("alert")).toHaveTextContent("临时失败");
    shouldFail = false;
    fireEvent.click(screen.getByRole("button", { name: "刷新" }));
    expect(await screen.findByRole("article", { name: "XIAO ESP32S3" })).toBeInTheDocument();
    expect(requests(fetchMock, "/api/hardware/mechanical-profiles")).toHaveLength(2);
  });

  it("Hardware Skill 保存后自动刷新机械档案投影", async () => {
    const fetchMock = mechanicalFetch();
    vi.stubGlobal("fetch", fetchMock);
    render(<MechanicalProfileLibrary />);

    expect(await screen.findByRole("article", { name: "XIAO ESP32S3" })).toBeInTheDocument();
    act(() => {
      window.dispatchEvent(new CustomEvent(HARDWARE_SKILL_UPDATED_EVENT));
    });

    await waitFor(() =>
      expect(requests(fetchMock, "/api/hardware/mechanical-profiles")).toHaveLength(2),
    );
  });
});

function mechanicalFetch({
  getProfiles = () => [profile()],
  onPut,
  onDelete,
  previewError,
}: {
  getProfiles?: () => MechanicalProfileSummary[];
  onPut?: (hardwareId: string) => void;
  onDelete?: (hardwareId: string) => void;
  previewError?: string;
} = {}) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.endsWith("/api/hardware/mechanical-profiles") && method === "GET") {
      try {
        return json({ profiles: getProfiles() });
      } catch (error) {
        return json(
          { detail: { code: "MECHANICAL_PROFILE_UNAVAILABLE", message: String(error) } },
          503,
        );
      }
    }
    if (url.endsWith("/api/hardware") && method === "GET") {
      return json({ components: hardwareComponents() });
    }
    const previewMatch = url.match(/\/api\/hardware\/mechanical-profiles\/([^/]+)\/preview$/);
    if (previewMatch && method === "POST") {
      if (previewError) {
        return json(
          { detail: { code: "MECHANICAL_PREVIEW_GENERATION_INVALID", message: previewError } },
          422,
        );
      }
      return json({ profile: profile(), generationSource: "DESCRIPTION_CACHE" });
    }
    const linkMatch = url.match(/\/api\/hardware\/([^/]+)\/mechanical-profile-link$/);
    if (linkMatch && method === "PUT") {
      const hardwareId = decodeURIComponent(linkMatch[1] ?? "");
      onPut?.(hardwareId);
      const body = JSON.parse(String(init?.body)) as { profileId: string; revision: string };
      return json({ hardwareId, ...body, confirmed: true });
    }
    if (linkMatch && method === "DELETE") {
      const hardwareId = decodeURIComponent(linkMatch[1] ?? "");
      onDelete?.(hardwareId);
      return json({ hardwareId, removed: true });
    }
    return json({}, 404);
  });
}

function requests(fetchMock: ReturnType<typeof vi.fn>, suffix: string) {
  return fetchMock.mock.calls.filter(([target]) => String(target).endsWith(suffix));
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

function profile(overrides: Partial<MechanicalProfileSummary> = {}): MechanicalProfileSummary {
  return {
    profileId: "xiao_esp32s3",
    revision: "xiao-revision-7",
    displayName: "XIAO ESP32S3",
    category: "mcu",
    dimensions: { length_x: 21, width_y: 17.8, height_z: 3.5 },
    mountingMode: "base_floor",
    mountingStrategy: "edge_retainer",
    preferredSurface: "base_floor",
    allowedSurfaces: ["base_floor", "lid_inner"],
    clearance: 0.5,
    evidenceLevel: "TRUSTED",
    representation: "parametric_envelope",
    coordinateSystem: {
      origin: "envelope_center",
      x_axis: "length",
      y_axis: "width",
      positive_z: "height",
    },
    modelKind: "envelope",
    previewGeometry: {
      primitives: [
        {
          primitive_id: "pcb",
          operation: "add",
          kind: "rounded_box",
          center: { x: 0, y: 0, z: 0.5 },
          size: { length_x: 21, width_y: 17.8, height_z: 1 },
          corner_radius: 2,
          rotation_z_deg: 0,
          role: "pcb",
        },
      ],
    },
    mountingHoles: [],
    openings: [],
    keepouts: [],
    contentSha256: "a".repeat(64),
    confirmedHardwareIds: ["hw-free", "hw-locked"],
    lockedHardwareIds: ["hw-locked"],
    ...overrides,
  };
}

function hardwareComponents(): HardwareComponent[] {
  return [
    hardwareComponent("hw-free", "旧按钮"),
    hardwareComponent("hw-locked", "K10"),
    hardwareComponent("hw-new", "新按钮"),
  ];
}

function hardwareComponent(id: string, name: string): HardwareComponent {
  return {
    id,
    name,
    category: HardwareCategory.MCU,
    status: HardwareComponentStatus.ACTIVE,
    electrical: {
      voltage: 3.3,
      logicLevel: 3.3,
      peakCurrent: 0.2,
      communicationProtocol: "GPIO",
      i2cAddress: null,
      supportedMCUs: [],
      driverName: null,
      firmwareRequirement: null,
    },
    stock: 1,
    price: 1,
    ageRecommendation: null,
    safetyTags: [],
    notes: "",
    createdAt: "2026-07-13T00:00:00Z",
    updatedAt: "2026-07-13T00:00:00Z",
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
