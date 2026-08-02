import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "../components/layout/AppShell";

vi.mock("../hooks/useHealthCheck", () => ({
  useHealthCheck: () => ({ status: "ok" as const, version: "0.1.0" }),
}));

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

describe("项目工作区", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("未选择项目时中央只显示主对话空状态，创建入口位于顶栏覆盖层", async () => {
    mockProjectFetch({ initiallyEmpty: true });
    render(<AppShell />);

    expect(await screen.findByText("开始一个创客项目")).toBeInTheDocument();
    const center = within(screen.getByTestId("center-chat"));

    expect(center.queryByLabelText("项目名称")).not.toBeInTheDocument();
    expect(center.queryByLabelText("创意描述")).not.toBeInTheDocument();
    expect(center.queryByRole("button", { name: "创建项目" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("新项目创意")).not.toBeInTheDocument();
    const dialog = openProjectCreation();
    expect(within(dialog).getByLabelText("新项目创意")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "分析并推荐" })).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "开始项目" })).toBeInTheDocument();
  });

  it("顶栏可以创建项目，创建后自动选中新项目并保持 CenterChat 常驻", async () => {
    const fetchMock = mockProjectFetch({ initiallyEmpty: true });
    render(<AppShell />);

    await screen.findByText("开始一个创客项目");
    const center = screen.getByTestId("center-chat");
    openProjectCreation();

    fireEvent.change(screen.getByLabelText("新项目创意"), {
      target: { value: "ESP32 温湿度 MQTT" },
    });
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).endsWith("/api/projects/suggest"),
      ),
    ).toHaveLength(0);
    expect(screen.getByRole("button", { name: "开始项目" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "分析并推荐" }));
    const projectNameInput = await screen.findByLabelText("项目名称");
    await waitFor(() =>
      expect(projectNameInput).toHaveValue("ESP32 温湿度 MQTT 装置")
    );
    expect(screen.getByText("掌问将协助完成")).toBeInTheDocument();
    expect(screen.queryByText("智能工程师")).not.toBeInTheDocument();
    expect(screen.queryByText("创想家")).not.toBeInTheDocument();
    expect(screen.queryByText("开源硬件设计师")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "开始项目" }));

    await screen.findAllByText("新项目");
    const createCall = fetchMock.mock.calls.find(([input, init]) => {
      const url = String(input);
      return url.endsWith("/api/projects") && init?.method === "POST";
    });
    expect(createCall).toBeDefined();
    const createBody = JSON.parse(String(createCall?.[1]?.body ?? "{}"));
    expect(createBody).toMatchObject({
      name: "ESP32 温湿度 MQTT 装置",
      initialIdea: "ESP32 温湿度 MQTT",
      selectedHardwareIds: [],
      selectedExpertTypes: ["smart_engineer"],
      initialExpert: "smart_engineer",
      expertSelectionMode: "auto",
      routerResult: {
        initialExpert: "smart_engineer",
        recommendedExperts: ["smart_engineer"],
      },
    });
    expect(createBody.idempotencyKey).toEqual(expect.any(String));
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/projects"),
      expect.objectContaining({ method: "POST" })
    );
    expect(screen.getByTestId("center-chat")).toBe(center);
    expect(within(screen.getByTestId("center-chat")).queryByTestId("project-center-overview")).not.toBeInTheDocument();
    expect(screen.getByTestId("chat-input")).toBeInTheDocument();
    expect(within(screen.getByTestId("center-chat")).getByText(/我会从实现方案开始推进/)).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "项目智能体" })).not.toBeInTheDocument();
    expect(within(screen.getByTestId("center-chat")).queryByText("开始一个创客项目")).not.toBeInTheDocument();
  });

  it("分析推荐完成后再选择硬件，选择变化不使推荐失效", async () => {
    const fetchMock = mockProjectFetch({ initiallyEmpty: true });
    render(<AppShell />);

    await screen.findByText("开始一个创客项目");
    const dialog = within(openProjectCreation());
    expect(dialog.queryByRole("button", { name: "选择项目硬件" })).not.toBeInTheDocument();
    expect(dialog.queryByRole("checkbox", { name: /ESP32 DevKit/ })).not.toBeInTheDocument();
    fireEvent.change(dialog.getByLabelText("新项目创意"), {
      target: { value: "做一个室内环境提醒器" },
    });
    fireEvent.click(dialog.getByRole("button", { name: "分析并推荐" }));
    expect(await dialog.findByLabelText("项目名称")).toBeInTheDocument();

    const firstSuggestCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        String(input).endsWith("/api/projects/suggest") && init?.method === "POST",
    );
    expect(JSON.parse(String(firstSuggestCall?.[1]?.body ?? "{}"))).toMatchObject({
      selectedHardwareIds: [],
    });

    fireEvent.click(dialog.getByRole("button", { name: "选择项目硬件" }));
    const hardwareDialog = within(await screen.findByRole("dialog", { name: "选择项目硬件" }));
    expect(hardwareDialog.getByRole("button", { name: "全部" })).toBeInTheDocument();
    expect(hardwareDialog.getByRole("button", { name: "传感器" })).toBeInTheDocument();
    fireEvent.click(hardwareDialog.getByRole("checkbox", { name: /ESP32 DevKit/ }));
    fireEvent.click(hardwareDialog.getByRole("checkbox", { name: /BME280/ }));
    expect(hardwareDialog.getByText("已选 2 项")).toBeInTheDocument();
    fireEvent.click(hardwareDialog.getByRole("button", { name: "确认选择" }));

    expect(await dialog.findByLabelText("项目名称")).toBeInTheDocument();
    expect(await dialog.findByText("已选择 2 项项目硬件")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(
        ([input, init]) =>
          String(input).endsWith("/api/hardware/validate") && init?.method === "POST",
      ),
    ).toBe(true);
    fireEvent.click(dialog.getByRole("button", { name: "开始项目" }));

    await screen.findAllByText("新项目");
    const createCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        String(input).endsWith("/api/projects") && init?.method === "POST",
    );
    expect(JSON.parse(String(createCall?.[1]?.body ?? "{}"))).toMatchObject({
      selectedHardwareIds: ["hw_bme280", "hw_esp32"],
    });
  });

  it("选择项目硬件时立即显示本地规则警告并阻止失败组合", async () => {
    mockProjectFetch({
      initiallyEmpty: true,
      hardwareValidation: "WARNING",
    });
    render(<AppShell />);
    await screen.findByText("开始一个创客项目");
    const dialog = within(openProjectCreation());
    fireEvent.change(dialog.getByLabelText("新项目创意"), {
      target: { value: "做一个环境提醒器" },
    });
    fireEvent.click(dialog.getByRole("button", { name: "分析并推荐" }));
    await dialog.findByLabelText("项目名称");
    fireEvent.click(dialog.getByRole("button", { name: "选择项目硬件" }));
    let hardwareDialog = within(await screen.findByRole("dialog", { name: "选择项目硬件" }));
    fireEvent.click(hardwareDialog.getByRole("checkbox", { name: /ESP32 DevKit/ }));
    fireEvent.click(hardwareDialog.getByRole("button", { name: "确认选择" }));
    expect(await hardwareDialog.findByText(/未选择供电模块/)).toBeInTheDocument();
    fireEvent.click(hardwareDialog.getByRole("button", { name: "完成" }));
    expect(await dialog.findByText(/未选择供电模块/)).toBeInTheDocument();

  });

  it("失败的硬件组合留在选择器中且不能写入创建表单", async () => {
    mockProjectFetch({ initiallyEmpty: true, hardwareValidation: "FAIL" });
    render(<AppShell />);
    await screen.findByText("开始一个创客项目");
    const dialog = within(openProjectCreation());
    fireEvent.change(dialog.getByLabelText("新项目创意"), {
      target: { value: "做一个环境提醒器" },
    });
    fireEvent.click(dialog.getByRole("button", { name: "分析并推荐" }));
    await dialog.findByLabelText("项目名称");
    fireEvent.click(dialog.getByRole("button", { name: "选择项目硬件" }));
    const hardwareDialog = within(await screen.findByRole("dialog", { name: "选择项目硬件" }));
    fireEvent.click(hardwareDialog.getByRole("checkbox", { name: /ESP32 DevKit/ }));
    fireEvent.click(hardwareDialog.getByRole("button", { name: "确认选择" }));
    expect(await hardwareDialog.findByRole("alert")).toHaveTextContent("电压不兼容");
    expect(dialog.getByText("尚未选择，可在规划缺件时再补充")).toBeInTheDocument();
  });

  it("创建请求进行中禁止直接关闭新建项目", async () => {
    const fetchMock = mockProjectFetch({ initiallyEmpty: true });
    const fallback = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/projects") && init?.method === "POST") {
        return new Promise<Response>(() => undefined);
      }
      if (!fallback) throw new Error(`未处理的测试请求：${url}`);
      return fallback(input, init);
    });

    render(<AppShell />);
    await screen.findByText("开始一个创客项目");
    const dialog = within(openProjectCreation());
    fireEvent.change(dialog.getByLabelText("新项目创意"), {
      target: { value: "做一个环境提醒器" },
    });
    fireEvent.click(dialog.getByRole("button", { name: "分析并推荐" }));
    await dialog.findByLabelText("项目名称");
    fireEvent.click(dialog.getByRole("button", { name: "开始项目" }));

    expect(dialog.getByRole("button", { name: "创建中..." })).toBeDisabled();
    expect(dialog.getByRole("button", { name: "关闭新建项目" })).toBeDisabled();
    expect(dialog.getByRole("button", { name: "取消" })).toBeDisabled();
  });

  it("用户手动修改名称和专家后，后续路由结果不会覆盖", async () => {
    mockProjectFetch({ initiallyEmpty: true });
    render(<AppShell />);

    fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "专业模式" }));
    fireEvent.click(screen.getByRole("button", { name: "关闭设置" }));

    openProjectCreation();
    fireEvent.change(await screen.findByLabelText("新项目创意"), {
      target: { value: "ESP32 温湿度 MQTT" },
    });
    fireEvent.click(screen.getByRole("button", { name: "分析并推荐" }));
    const nameInput = await screen.findByLabelText("项目名称");
    await waitFor(() =>
      expect(nameInput).toHaveValue("ESP32 温湿度 MQTT 装置")
    );

    fireEvent.change(nameInput, { target: { value: "我的手动项目名" } });
    fireEvent.click(screen.getByRole("button", { name: "调整专家" }));
    const expertList = within(screen.getByLabelText("推荐参与专家"));
    const checkboxes = expertList.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(3);
    const smartCheckbox = checkboxes[1] as HTMLInputElement;
    const structureCheckbox = checkboxes[2] as HTMLInputElement;
    fireEvent.click(structureCheckbox);
    fireEvent.click(smartCheckbox);

    fireEvent.change(screen.getByLabelText("新项目创意"), {
      target: { value: "只设计 ESP32 外壳 STL" },
    });

    expect(screen.queryByLabelText("项目名称")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "开始项目" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "分析并推荐" }));
    expect(await screen.findByLabelText("项目名称")).toHaveValue("我的手动项目名");
    const refreshedExpertList = within(screen.getByLabelText("推荐参与专家"));
    const refreshedCheckboxes = refreshedExpertList.getAllByRole("checkbox");
    expect(refreshedCheckboxes[2]).toBeChecked();
    expect(refreshedCheckboxes[1]).not.toBeChecked();
  });

  it("创建页至少保留一位专家", async () => {
    mockProjectFetch({ initiallyEmpty: true });
    render(<AppShell />);

    fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "专业模式" }));
    fireEvent.click(screen.getByRole("button", { name: "关闭设置" }));

    openProjectCreation();
    fireEvent.change(await screen.findByLabelText("新项目创意"), {
      target: { value: "我不知道做什么项目" },
    });
    fireEvent.click(screen.getByRole("button", { name: "分析并推荐" }));
    const projectNameInput = await screen.findByLabelText("项目名称");
    await waitFor(() => expect(projectNameInput).toHaveValue("我不知道做什么项目项目"));

    fireEvent.click(screen.getByRole("button", { name: "调整专家" }));
    const guideCheckbox = within(screen.getByLabelText("推荐参与专家")).getAllByRole(
      "checkbox"
    )[0] as HTMLInputElement;
    fireEvent.click(guideCheckbox);

    const dialog = within(screen.getByRole("dialog", { name: "新建项目" }));
    expect(await dialog.findByRole("alert")).toHaveTextContent("至少选择一位专家");
    expect(guideCheckbox).toBeChecked();
  });

  it("创建失败时错误显示在左侧创建区域", async () => {
    mockProjectFetch({ initiallyEmpty: true, failCreate: true });
    render(<AppShell />);

    openProjectCreation();
    fireEvent.change(await screen.findByLabelText("新项目创意"), {
      target: { value: "失败项目" },
    });
    fireEvent.click(screen.getByRole("button", { name: "分析并推荐" }));
    const projectNameInput = await screen.findByLabelText("项目名称");
    await waitFor(() => expect(projectNameInput).toHaveValue("失败项目项目"));
    fireEvent.click(screen.getByRole("button", { name: "开始项目" }));

    const dialog = within(screen.getByRole("dialog", { name: "新建项目" }));
    expect(await dialog.findByRole("alert")).toHaveTextContent("API 请求失败");
    expect(within(screen.getByTestId("center-chat")).getByText("开始一个创客项目")).toBeInTheDocument();
  });

  it("项目建议失败时不生成本地替代建议并禁止创建", async () => {
    const fetchMock = mockProjectFetch({ initiallyEmpty: true, failSuggest: true });
    render(<AppShell />);

    await screen.findByText("开始一个创客项目");
    openProjectCreation();
    fireEvent.change(await screen.findByLabelText("新项目创意"), {
      target: { value: "需要云端分析的项目" },
    });
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        String(input).endsWith("/api/projects/suggest"),
      ),
    ).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "分析并推荐" }));

    const dialog = within(screen.getByRole("dialog", { name: "新建项目" }));
    expect(await dialog.findByRole("alert")).toHaveTextContent("LLM_OUTPUT_INVALID");
    expect(dialog.queryByLabelText("项目名称")).not.toBeInTheDocument();
    expect(dialog.getByRole("button", { name: "开始项目" })).toBeDisabled();
    expect(
      fetchMock.mock.calls.filter(([input, init]) =>
        String(input).endsWith("/api/projects") && (init?.method ?? "GET") === "POST"
      )
    ).toHaveLength(0);
  });

  it("切换项目时恢复各项目独立草稿并保持右侧 Tab 行为", async () => {
    mockProjectFetch();
    render(<AppShell />);

    await screen.findAllByText("项目甲");
    const center = screen.getByTestId("center-chat");
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue("甲草稿");

    fireEvent.change(screen.getByLabelText("切换项目"), {
      target: { value: "prj_b" },
    });
    await screen.findAllByText("项目乙");
    expect(screen.getByTestId("center-chat")).toBe(center);
    await waitFor(() =>
      expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue("乙草稿")
    );

    fireEvent.click(screen.getByRole("tab", { name: "产物" }));
    expect(screen.getByTestId("center-chat")).toBe(center);
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue("乙草稿");

    fireEvent.change(screen.getByLabelText("切换项目"), {
      target: { value: "prj_a" },
    });
    await waitFor(() =>
      expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue("甲草稿")
    );
    expect(screen.getByTestId("center-chat")).toBe(center);
  });

  it("生成中切换项目会先取消并收敛原请求，再打开目标项目", async () => {
    const fetchMock = mockProjectFetch();
    const fallback = fetchMock.getMockImplementation();
    const events: string[] = [];
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/projects/prj_a/chat/stream") && method === "POST") {
        const body = JSON.parse(String(init?.body ?? "{}"));
        const chunk = {
          type: "START",
          requestId: "req_switch",
          projectId: "prj_a",
          conversationId: conversationId("prj_a", "problem_guide"),
          messageId: "msg_stream_switch",
          requestTurnId: body.clientTurnId,
          responseTurnId: "turn_response_switch",
          model: "deepseek-v4-flash",
        };
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            controller.enqueue(
              new TextEncoder().encode(`event: chat.started\ndata: ${JSON.stringify(chunk)}\n\n`),
            );
          },
          cancel() {
            events.push("stream-canceled");
          },
        });
        return new Response(stream, {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        });
      }
      if (url.endsWith("/api/projects/prj_a/chat/cancel/req_switch") && method === "POST") {
        events.push("cancel-request");
        return json({ requestId: "req_switch", canceled: true });
      }
      if (url.endsWith("/api/projects/prj_b/open") && method === "POST") {
        events.push("open-target");
      }
      if (!fallback) throw new Error(`未处理的测试请求：${url}`);
      return fallback(input, init);
    });

    render(<AppShell />);
    await screen.findAllByText("项目甲");
    const input = screen.getByPlaceholderText("描述你想做的作品…");
    fireEvent.change(input, { target: { value: "请继续分析" } });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    expect(await screen.findByRole("button", { name: "停止" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("切换项目"), {
      target: { value: "prj_b" },
    });
    const confirmation = await screen.findByRole("dialog", { name: "切换项目" });
    expect(confirmation).toHaveTextContent("先停止生成并保存草稿");
    fireEvent.click(within(confirmation).getByRole("button", { name: "切换" }));

    await waitFor(() => expect(screen.getByLabelText("切换项目")).toHaveValue("prj_b"));
    expect(events).toEqual(["stream-canceled", "cancel-request", "open-target"]);
    expect(screen.getByTestId("center-chat")).toBeInTheDocument();
  });

  it("草稿保存失败可见、可重试，切换前要求明确放弃", async () => {
    const fetchMock = mockProjectFetch();
    const fallback = fetchMock.getMockImplementation();
    let failDraftSave = true;
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (
        failDraftSave &&
        url.endsWith("/api/projects/prj_a/draft") &&
        init?.method === "PUT"
      ) {
        return json({
          detail: {
            code: "DRAFT_SAVE_FAILED",
            message: "测试草稿写入失败。",
            retryable: true,
          },
        }, 503);
      }
      if (!fallback) throw new Error(`未处理的测试请求：${url}`);
      return fallback(input, init);
    });

    render(<AppShell />);
    await screen.findAllByText("项目甲");
    const input = screen.getByPlaceholderText("描述你想做的作品…");
    fireEvent.change(input, { target: { value: "尚未持久化的草稿" } });
    expect(screen.getByText("未保存")).toBeInTheDocument();
    expect(await screen.findByText("保存失败", {}, { timeout: 2000 })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("切换项目"), {
      target: { value: "prj_b" },
    });
    const confirmation = await screen.findByRole("dialog", { name: "切换项目" });
    expect(confirmation).toHaveTextContent("放弃尚未保存的内容");
    fireEvent.click(within(confirmation).getByRole("button", { name: "取消" }));
    expect(screen.getByLabelText("切换项目")).toHaveValue("prj_a");

    failDraftSave = false;
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(await screen.findByText("已保存")).toBeInTheDocument();
  });

  it("从公共知识打开 Hardware Skill 浮窗时保持中央对话与草稿", async () => {
    mockProjectFetch();
    render(<AppShell />);

    await screen.findAllByText("项目甲");
    const center = screen.getByTestId("center-chat");
    const input = screen.getByPlaceholderText("描述你想做的作品…");
    expect(input).toHaveValue("甲草稿");

    fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "专业模式" }));
    fireEvent.click(screen.getByRole("button", { name: "公共知识" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "查看 ESP32 DevKit" }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "打开 Skill 项目 ESP32 DevKit" }),
    );

    expect(
      screen.getByRole("dialog", { name: "ESP32 DevKit · Hardware Skill" }),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("settings-dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(center);
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue("甲草稿");
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(
      expect.arrayContaining(["工作", "产物", "设备"]),
    );

    fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
    const reopenedSettings = screen.getByRole("dialog", { name: "设置" });
    const professionalMode = within(reopenedSettings).getByRole("checkbox", {
      name: "专业模式",
    });
    expect(professionalMode).toBeChecked();
    fireEvent.click(professionalMode);
    await waitFor(() => expect(
      screen.queryByRole("dialog", { name: "ESP32 DevKit · Hardware Skill" }),
    ).not.toBeInTheDocument());
    expect(professionalMode).not.toBeChecked();
    expect(screen.queryByText("manifest.json（系统只读）")).not.toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(center);
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue("甲草稿");
  });

  it("从机械档案打开 3D 预览浮窗时保持中央对话、草稿和右侧三 Tab", async () => {
    mockProjectFetch();
    render(<AppShell />);

    await screen.findAllByText("项目甲");
    const center = screen.getByTestId("center-chat");
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue("甲草稿");

    fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "专业模式" }));
    fireEvent.click(screen.getByRole("button", { name: "公共知识" }));
    fireEvent.click(screen.getByRole("tab", { name: "机械档案" }));
    const profile = await screen.findByRole("article", { name: "XIAO ESP32S3" });
    fireEvent.click(
      within(profile).getByRole("button", { name: "查看 XIAO ESP32S3 3D 预览" }),
    );

    expect(
      await screen.findByRole("dialog", { name: "XIAO ESP32S3 · 机械档案预览" }),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("settings-dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(center);
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue("甲草稿");
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(
      expect.arrayContaining(["工作", "产物", "设备"]),
    );
  });

  it("归档项目时弹出确认对话框，确认后才执行", async () => {
    mockProjectFetch();
    render(<AppShell />);

    await screen.findAllByText("项目甲");
    openProjectTools();

    fireEvent.click(screen.getByRole("button", { name: "归档项目" }));
    expect(screen.getByRole("dialog", { name: "归档项目" })).toBeInTheDocument();
    expect(screen.getByText(/确定归档项目“项目甲”/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "归档" }));

    await waitFor(() =>
      expect(screen.queryByRole("option", { name: "项目甲" })).not.toBeInTheDocument()
    );
  });

  it("左栏独立归档并恢复项目，自动切换可用项目且保留原草稿", async () => {
    const fetchMock = mockProjectFetch();
    render(<AppShell />);

    await screen.findAllByText("项目甲");
    const center = screen.getByTestId("center-chat");
    const left = within(screen.getByTestId("left-sidebar"));

    fireEvent.click(left.getByRole("button", { name: "归档项目 项目甲" }));
    const confirmation = screen.getByRole("dialog", { name: "归档项目" });
    expect(confirmation).toHaveTextContent("不会永久删除，可随时恢复");
    expect(
      fetchMock.mock.calls.filter(([target]) => String(target).endsWith("/archive"))
    ).toHaveLength(0);

    fireEvent.click(within(confirmation).getByRole("button", { name: "归档" }));

    await waitFor(() => expect(screen.getByLabelText("切换项目")).toHaveValue("prj_b"));
    expect(screen.getByTestId("center-chat")).toBe(center);
    await waitFor(() =>
      expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue("乙草稿")
    );
    expect(screen.queryByRole("option", { name: "项目甲" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("已归档项目（1）"));
    fireEvent.click(screen.getByRole("button", { name: "恢复项目 项目甲" }));

    expect(await screen.findByRole("option", { name: "项目甲" })).toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(center);
    fireEvent.change(screen.getByLabelText("切换项目"), {
      target: { value: "prj_a" },
    });
    await waitFor(() =>
      expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue("甲草稿")
    );
    expect(screen.getByTestId("center-chat")).toBe(center);
  });

  it("取消归档不改变项目列表", async () => {
    mockProjectFetch();
    render(<AppShell />);

    await screen.findAllByText("项目甲");
    openProjectTools();
    fireEvent.click(screen.getByRole("button", { name: "归档项目" }));
    expect(screen.getByRole("dialog", { name: "归档项目" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "取消" }));

    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "归档项目" })).not.toBeInTheDocument()
    );
    expect(screen.getByRole("option", { name: "项目甲" })).toBeInTheDocument();
  });

  it("项目工具通过明确操作重命名项目", async () => {
    mockProjectFetch();
    render(<AppShell />);

    await screen.findAllByText("项目甲");
    openProjectTools();

    const renameInput = screen.getByLabelText("项目工具中的项目名称");
    expect(renameInput).toBeInTheDocument();
    expect(renameInput).toHaveValue("项目甲");

    fireEvent.change(renameInput, { target: { value: "改名后甲" } });
    fireEvent.click(screen.getByRole("button", { name: "重命名项目" }));

    expect(await screen.findByRole("option", { name: "改名后甲" })).toBeInTheDocument();
  });

  it("关闭项目工具不会提交未确认的重命名", async () => {
    mockProjectFetch();
    render(<AppShell />);

    await screen.findAllByText("项目甲");
    const tools = openProjectTools();

    const renameInput = screen.getByLabelText("项目工具中的项目名称");
    fireEvent.change(renameInput, { target: { value: "不应生效" } });
    fireEvent.click(within(tools).getByRole("button", { name: "关闭项目工具" }));

    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "项目工具" })).not.toBeInTheDocument()
    );
    expect(screen.getByRole("option", { name: "项目甲" })).toBeInTheDocument();
  });

  it("项目工具可以导出当前项目包并保持 CenterChat 常驻", async () => {
    const fetchMock = mockProjectFetch();
    render(<AppShell />);

    await screen.findAllByText("项目甲");
    const center = screen.getByTestId("center-chat");
    openProjectTools();

    fireEvent.click(screen.getByRole("button", { name: "导出当前项目包" }));

    expect(
      await screen.findByText("已导出 zhangwen-project-pkg_test.zip")
    ).toBeInTheDocument();
    expect(screen.getByLabelText("项目包 Base64")).toHaveValue("UEsDBAo=");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/projects/prj_a/package/export"),
      expect.objectContaining({ method: "POST" })
    );
    expect(screen.getByTestId("center-chat")).toBe(center);
  });

  it("项目工具可以导入项目包副本并保持 CenterChat 常驻", async () => {
    const fetchMock = mockProjectFetch();
    render(<AppShell />);

    await screen.findAllByText("项目甲");
    const center = screen.getByTestId("center-chat");
    openProjectTools();
    fireEvent.change(screen.getByLabelText("项目包 Base64"), {
      target: { value: "UEsDBAo=" },
    });

    fireEvent.click(screen.getByRole("button", { name: "导入项目包" }));

    expect(await screen.findByText("已导入 导入项目")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/projects/package/import"),
      expect.objectContaining({ method: "POST" })
    );
    expect(await screen.findAllByText("导入项目")).not.toHaveLength(0);
    expect(screen.getByTestId("center-chat")).toBe(center);
  });

  it("项目工具可以把电子器件加入当前项目并保持 CenterChat 常驻", async () => {
    const fetchMock = mockProjectFetch();
    render(<AppShell />);

    await screen.findAllByText("项目甲");
    const center = screen.getByTestId("center-chat");
    const tools = openProjectTools();
    fireEvent.click(
      within(tools).getByRole("button", { name: "管理项目硬件" }),
    );

    const selector = within(
      await screen.findByRole("dialog", { name: "添加项目电子器件" }),
    );
    fireEvent.click(selector.getByRole("checkbox", { name: /ESP32 DevKit/ }));
    fireEvent.click(selector.getByRole("checkbox", { name: /BME280/ }));
    fireEvent.click(selector.getByRole("button", { name: "添加到项目" }));

    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: "添加项目电子器件" }),
      ).not.toBeInTheDocument(),
    );
    const updateCall = fetchMock.mock.calls.find(
      ([input, init]) =>
        String(input).endsWith("/api/projects/prj_a/hardware") &&
        init?.method === "PUT",
    );
    expect(JSON.parse(String(updateCall?.[1]?.body ?? "{}"))).toEqual({
      selectedHardwareIds: ["hw_bme280", "hw_esp32"],
    });
    expect(screen.getByTestId("center-chat")).toBe(center);
  });

  it("项目工具使用 Hardware Skill 浮窗，并在最小化或关闭时保护未保存 Markdown", async () => {
    mockProjectFetch();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<AppShell />);

    await screen.findAllByText("项目甲");
    const center = screen.getByTestId("center-chat");
    fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "专业模式" }));
    fireEvent.click(screen.getByRole("button", { name: "关闭设置" }));
    const tools = openProjectTools();
    fireEvent.click(
      await within(tools).findByRole("button", { name: "查看 ESP32 DevKit" }),
    );
    fireEvent.click(
      await within(tools).findByRole("button", {
        name: "打开 Skill 项目 ESP32 DevKit",
      }),
    );

    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "项目工具" })).not.toBeInTheDocument(),
    );
    const floating = await screen.findByRole("dialog", {
      name: "ESP32 DevKit · Hardware Skill",
    });
    const editor = await within(floating).findByLabelText("编辑 SKILL.md");
    fireEvent.change(editor, { target: { value: "# 未保存的器件说明" } });

    fireEvent.click(within(floating).getByRole("button", { name: "最小化浮窗" }));
    fireEvent.click(within(floating).getByRole("button", { name: "最小化浮窗" }));
    expect(within(floating).getByLabelText("编辑 SKILL.md")).toHaveValue(
      "# 未保存的器件说明",
    );

    fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
    const modeSettings = screen.getByRole("dialog", { name: "设置" });
    const professionalMode = within(modeSettings).getByRole("checkbox", {
      name: "专业模式",
    });
    fireEvent.click(professionalMode);
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining("关闭专业模式"));
    expect(professionalMode).toBeChecked();
    expect(screen.getByRole("dialog", { name: "ESP32 DevKit · Hardware Skill" }))
      .toBeInTheDocument();
    expect(within(floating).getByLabelText("编辑 SKILL.md")).toHaveValue(
      "# 未保存的器件说明",
    );
    fireEvent.click(within(modeSettings).getByRole("button", { name: "关闭设置" }));

    fireEvent.click(within(floating).getByRole("button", { name: "关闭浮窗" }));
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining("有未保存修改"));
    expect(screen.getByRole("dialog", { name: "ESP32 DevKit · Hardware Skill" })).toBeInTheDocument();

    confirmSpy.mockReturnValue(true);
    fireEvent.click(within(floating).getByRole("button", { name: "关闭浮窗" }));
    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: "ESP32 DevKit · Hardware Skill" }),
      ).not.toBeInTheDocument(),
    );
    expect(screen.getByTestId("center-chat")).toBe(center);
  });

  it("Sidecar 不可用时显示错误并可重试", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new Error("网络不可用");
      })
    );
    render(<AppShell />);

    const errorAlert = await screen.findByRole("alert");
    expect(errorAlert).toHaveTextContent("本地服务未连接");

    expect(screen.getByRole("button", { name: "重试" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "关闭" }));
    await waitFor(() =>
      expect(screen.queryByRole("alert")).not.toBeInTheDocument()
    );
  });
});

function openProjectCreation() {
  fireEvent.click(
    within(screen.getByTestId("left-sidebar")).getByRole("button", { name: "新建项目" }),
  );
  return screen.getByRole("dialog", { name: "新建项目" });
}

function openProjectTools() {
  fireEvent.click(screen.getByRole("button", { name: "项目工具" }));
  return screen.getByRole("dialog", { name: "项目工具" });
}

function mockProjectFetch({
  initiallyEmpty = false,
  failCreate = false,
  failSuggest = false,
  hardwareValidation = "PASS",
}: {
  initiallyEmpty?: boolean;
  failCreate?: boolean;
  failSuggest?: boolean;
  hardwareValidation?: "PASS" | "WARNING" | "FAIL";
} = {}) {
  let activeProjectId = initiallyEmpty ? null : "prj_a";
  const drafts: Record<string, string> = {
    prj_a: "甲草稿",
    prj_b: "乙草稿",
    prj_new: "",
  };
  const projects = initiallyEmpty
    ? []
    : [
        summary("prj_a", "项目甲"),
        summary("prj_b", "项目乙"),
      ];
  const archivedProjects: ReturnType<typeof summary>[] = [];

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (url.endsWith("/api/settings/llm") && method === "GET") {
      return json({
        config: {
          provider: "deepseek",
          baseUrl: "https://api.deepseek.com",
          defaultModel: "deepseek-v4-flash",
          thinkingMode: "AUTO",
          reasoningEffort: null,
          timeoutSeconds: 60,
          keySaved: true,
          maskedApiKey: "sk-****alue",
          updatedAt: null,
        },
      });
    }

    if (url.endsWith("/api/llm/models")) {
      return json({
        models: [
          {
            id: "deepseek-v4-flash",
            label: "DeepSeek V4 Flash",
            provider: "deepseek",
            supportsThinking: true,
            supportsStreaming: true,
          },
        ],
      });
    }

    if (url.endsWith("/api/hardware/skills") && method === "GET") {
      return json({
        skills: [
          hardwareSkillSummary("esp32-devkit", "hw_esp32", "ESP32 DevKit", "MCU", "Wi-Fi 主控"),
          hardwareSkillSummary("bme280-sensor", "hw_bme280", "BME280 环境传感器", "SENSOR", "温湿度与气压"),
        ],
      });
    }

    if (url.endsWith("/api/hardware/skills/esp32-devkit") && method === "GET") {
      return json({ skill: hardwareSkill("esp32-devkit", "hw_esp32", "ESP32 DevKit", "MCU", "Wi-Fi 主控") });
    }

    if (url.endsWith("/api/hardware/skills/bme280-sensor") && method === "GET") {
      return json({ skill: hardwareSkill("bme280-sensor", "hw_bme280", "BME280 环境传感器", "SENSOR", "温湿度与气压") });
    }

    if (url.endsWith("/api/hardware") && method === "GET") {
      return json({
        components: [
          hardwareComponent("hw_esp32", "ESP32 DevKit", "MCU", "Wi-Fi 主控"),
          hardwareComponent("hw_bme280", "BME280 环境传感器", "SENSOR", "温湿度与气压"),
        ],
      });
    }

    if (url.endsWith("/api/hardware/mechanical-profiles") && method === "GET") {
      return json({ profiles: [mechanicalProfileSummary()] });
    }

    if (
      url.endsWith("/api/hardware/mechanical-profiles/xiao_esp32s3/preview") &&
      method === "POST"
    ) {
      return json({
        profile: mechanicalProfileSummary(),
        generationSource: "DESCRIPTION_CACHE",
      });
    }

    if (url.endsWith("/api/hardware/validate") && method === "POST") {
      const checks = hardwareValidation === "PASS"
        ? [{
            dimension: "component_exists",
            severity: "PASS",
            message: "硬件组合可用。",
            details: "",
          }]
        : hardwareValidation === "WARNING"
          ? [{
              dimension: "power",
              severity: "WARNING",
              message: "未选择供电模块",
              details: "请在接线前确认供电方式",
            }]
          : [{
              dimension: "voltage",
              severity: "FAIL",
              message: "电压不兼容",
              details: "5V 不能接入 3.3V",
            }];
      return json({
        result: {
          overall: hardwareValidation,
          message: hardwareValidation === "PASS" ? "硬件组合校验通过。" : "硬件组合需要处理。",
          checks,
        },
      });
    }

    if (
      (url.endsWith("/api/projects") ||
        url.endsWith("/api/projects?includeArchived=true")) &&
      method === "GET"
    ) {
      return json({
        activeProjectId,
        projects: url.includes("includeArchived=true")
          ? [...projects, ...archivedProjects]
          : projects,
      });
    }

    if (url.endsWith("/api/projects/suggest") && method === "POST") {
      if (failSuggest) {
        return json(
          {
            detail: {
              code: "LLM_OUTPUT_INVALID",
              message: "云端模型连续两次未返回有效结构，请重试。",
              retryable: true,
            },
          },
          422
        );
      }
      const body = JSON.parse(String(init?.body ?? "{}"));
      const idea = String(body.text ?? body.initialIdea ?? "");
      const suggestion = {
        ...suggestionForIdea(idea),
        selectedHardwareWarnings: Array.isArray(body.selectedHardwareIds) &&
          body.selectedHardwareIds.includes("hw_bme280")
          ? ["BME280 需要确认 I2C 地址冲突。"]
          : [],
      };
      return json({
        suggestion,
      });
    }

    if (url.endsWith("/api/projects") && method === "POST") {
      if (failCreate) {
        return json({ code: "PERSISTENCE_WRITE_FAILED", message: "创建失败" }, 500);
      }
      const body = JSON.parse(String(init?.body ?? "{}"));
      const selectedExpertTypes = body.selectedExpertTypes ?? ["problem_guide"];
      const initialExpert = body.initialExpert ?? selectedExpertTypes[0] ?? "problem_guide";
      projects.unshift(summary("prj_new", "新项目"));
      activeProjectId = "prj_new";
      return json({
        workspace: workspace(
          "prj_new",
          "新项目",
          drafts.prj_new ?? "",
          selectedExpertTypes,
          initialExpert,
          String(body.initialIdea ?? "")
        ),
      });
    }

    if (url.endsWith("/api/projects/package/import") && method === "POST") {
      projects.unshift(summary("prj_imported", "导入项目"));
      drafts.prj_imported = "";
      activeProjectId = "prj_imported";
      return json({
        package: packageRecord("pkg_import", "IMPORTED", null),
        workspace: workspace("prj_imported", "导入项目", ""),
      });
    }

    const projectId = projectIdFromUrl(url);
    if (projectId && url.endsWith("/package/export") && method === "POST") {
      return json({
        package: packageRecord("pkg_test", "EXPORTED", "UEsDBAo="),
      });
    }

    if (projectId && url.endsWith("/artifacts") && method === "GET") {
      return json({ artifacts: [] });
    }

    if (
      projectId &&
      url.endsWith(`/experts/${expertId(projectId)}/activate`) &&
      method === "POST"
    ) {
      return json({
        workspace: workspace(projectId, projectName(projectId), drafts[projectId] ?? ""),
      });
    }

    if (projectId && url.endsWith("/execution-plan/current") && method === "GET") {
      return json({ code: "EXECUTION_PLAN_NOT_FOUND" }, 404);
    }

    if (projectId && url.endsWith("/spec/current") && method === "GET") {
      return json({ code: "SPEC_NOT_FOUND" }, 404);
    }

    if (projectId && url.endsWith("/code/current") && method === "GET") {
      return json({ code: "CODE_NOT_FOUND" }, 404);
    }

    if (projectId && method === "GET") {
      return json({ workspace: workspace(projectId, projectName(projectId), drafts[projectId] ?? "") });
    }

    if (url.endsWith("/open") && method === "POST" && projectId) {
      activeProjectId = projectId;
      return json({ workspace: workspace(projectId, projectName(projectId), drafts[projectId] ?? "") });
    }

    if (url.endsWith("/draft") && method === "PUT" && projectId) {
      drafts[projectId] = JSON.parse(String(init?.body ?? "{}")).content ?? "";
      return json({ workspace: workspace(projectId, projectName(projectId), drafts[projectId] ?? "") });
    }

    if (url.endsWith("/hardware") && method === "PUT" && projectId) {
      const body = JSON.parse(String(init?.body ?? "{}"));
      const selectedHardwareIds = Array.isArray(body.selectedHardwareIds)
        ? body.selectedHardwareIds
        : [];
      const nextWorkspace = workspace(
        projectId,
        projectName(projectId),
        drafts[projectId] ?? "",
      );
      return json({
        workspace: {
          ...nextWorkspace,
          sharedContext: {
            ...nextWorkspace.sharedContext,
            confirmedFacts: [
              {
                id: `fact_hardware_${projectId}`,
                projectId,
                field: "preferred_hardware",
                key: "preferred_hardware",
                value: {
                  policy: "prefer_selected_and_fill_gaps",
                  components: selectedHardwareIds.map((id: string) => ({ id })),
                },
                status: "confirmed",
                sourceType: "user",
                confirmed: true,
                confirmedBy: "user",
                updatedAt: "2026-07-15T00:00:00.000Z",
              },
            ],
          },
        },
        selectedHardwareWarnings: [],
      });
    }

    if (url.endsWith("/archive") && method === "POST" && projectId) {
      const idx = projects.findIndex((p) => p.id === projectId);
      if (idx >= 0) {
        const [archived] = projects.splice(idx, 1);
        if (archived) {
          archived.archivedAt = "2026-07-11T00:00:00.000Z";
          archivedProjects.unshift(archived);
        }
      }
      if (activeProjectId === projectId) activeProjectId = projects[0]?.id ?? null;
      return json({ projects, activeProjectId });
    }

    if (url.endsWith("/restore") && method === "POST" && projectId) {
      const idx = archivedProjects.findIndex((project) => project.id === projectId);
      if (idx >= 0) {
        const [restored] = archivedProjects.splice(idx, 1);
        if (restored) {
          restored.archivedAt = null;
          projects.unshift(restored);
        }
      }
      activeProjectId ??= projectId;
      return json({ projects, activeProjectId });
    }

    if (method === "PATCH" && projectId) {
      const body = JSON.parse(String(init?.body ?? "{}"));
      const proj = projects.find((p) => p.id === projectId);
      if (proj && body.name) proj.name = body.name;
      return json({ workspace: workspace(projectId, body.name ?? projectName(projectId), drafts[projectId] ?? "") });
    }

    return json({}, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function summary(id: string, name: string, archivedAt: string | null = null) {
  return {
    id,
    name,
    stage: "IDEA",
    activeExpertIds: [expertId(id)],
    selectedModel: "deepseek-v4-flash",
    messageCount: 0,
    draftUpdatedAt: null,
    archivedAt,
    updatedAt: "2026-07-08T00:00:00.000Z",
    lastOpenedAt: "2026-07-08T00:00:00.000Z",
  };
}

function workspace(
  id: string,
  name: string,
  draft: string,
  selectedExpertTypes: string[] = ["problem_guide"],
  initialExpert: string = selectedExpertTypes[0] ?? "problem_guide",
  initialIdea = "测试创意"
) {
  const experts = selectedExpertTypes.map((expertType) => ({
    id: expertId(id, expertType),
    projectId: id,
    expertDefinitionId: `expert_def_${expertType}`,
    expertType,
    conversationId: conversationId(id, expertType),
    privateMemoryId: `memory_${id}_${expertType}`,
    status: expertType === initialExpert ? "working" : "idle",
    workspaceStatus: expertType === initialExpert ? "in_progress" : "not_started",
    currentTask: "继续推进项目",
    addedAt: "2026-07-08T00:00:00.000Z",
    removedAt: null,
  }));
  const activeExpert = experts.find((expert) => expert.expertType === initialExpert) ?? experts[0];
  const activeConversationId = activeExpert?.conversationId ?? conversationId(id);
  const activeMessages = initialIdea
    ? [
        {
          id: `msg_initial_${id}`,
          role: "user",
          content: initialIdea,
          status: "COMPLETED",
          createdAt: "2026-07-08T00:00:00.000Z",
          updatedAt: "2026-07-08T00:00:00.000Z",
        },
        {
          id: `msg_initial_assistant_${id}`,
          role: "assistant",
          content: "我会从实现方案开始推进。接下来会确认核心功能、硬件模块、供电与通信方式，以及第一版可验证的软件和硬件路径。",
          status: "COMPLETED",
          metadata: {
            source: "project_creation_runtime",
            initialExpert,
          },
          createdAt: "2026-07-08T00:00:00.000Z",
          updatedAt: "2026-07-08T00:00:00.000Z",
          model: "deepseek-v4-flash",
        },
      ]
    : [];
  return {
    project: {
      id,
      name,
      stage: "IDEA",
      profile: { initialIdea },
      conversationId: activeConversationId,
      activeExpertIds: experts.map((expert) => expert.id),
      activeExpertId: activeExpert?.id ?? null,
      sharedContextId: `shared_${id}`,
      coordinatorStateId: `coord_${id}`,
      selectedModel: "deepseek-v4-flash",
      archivedAt: null,
      createdAt: "2026-07-08T00:00:00.000Z",
      updatedAt: "2026-07-08T00:00:00.000Z",
      lastOpenedAt: "2026-07-08T00:00:00.000Z",
      schemaVersion: 22,
    },
    conversation: {
      id: activeConversationId,
      projectId: id,
      messages: activeMessages,
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
    draft: {
      projectId: id,
      projectExpertId: activeExpert?.id ?? null,
      content: draft,
      updatedAt: draft ? "2026-07-08T00:00:00.000Z" : null,
    },
    experts,
    expertDefinitions: expertDefinitions(),
    expertConversations: experts.map((expert) => {
      const definition = expertDefinitions().find((item) => item.type === expert.expertType);
      return {
        id: expert.conversationId,
        projectId: id,
        projectExpertId: expert.id,
        expertType: expert.expertType,
        expertName: definition?.name ?? expert.expertType,
        messages: expert.expertType === initialExpert ? activeMessages : [],
        draft: {
          projectId: id,
          projectExpertId: expert.id,
          content: expert.expertType === initialExpert ? draft : "",
          updatedAt: draft ? "2026-07-08T00:00:00.000Z" : null,
        },
        activeQuestionId: null,
        activeTurnId: null,
        updatedAt: "2026-07-08T00:00:00.000Z",
      };
    }),
    sharedContext: {
      id: `shared_${id}`,
      projectId: id,
      revision: 1,
      goals: [],
      constraints: [],
      requirements: [],
      decisions: [],
      activeArtifactVersions: [],
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
    coordinator: {
      id: `coord_${id}`,
      projectId: id,
      currentItem: {
        id: `item_${id}`,
        title: "继续回答问题引导师的问题",
        description: "保持项目只有一个当前事项。",
        targetExpertId: activeExpert?.id ?? null,
        targetArtifactId: null,
        actionLabel: "继续",
        severity: "info",
      },
      expertStatuses: experts,
      conflicts: [],
      dependencies: [],
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
  };
}

function suggestionForIdea(idea: string) {
  const hasSmartSignal = /esp32|mqtt|温湿度|传感|硬件|联网/i.test(idea);
  const hasStructureSignal = /外壳|结构|stl|3d|打印/i.test(idea);
  const initialExpert = hasStructureSignal && !hasSmartSignal
    ? "structure_engineer"
    : hasSmartSignal
      ? "smart_engineer"
      : "problem_guide";
  const recommendedExpertTypes = [
    ...(initialExpert === "problem_guide" ? ["problem_guide"] : []),
    ...(hasSmartSignal ? ["smart_engineer"] : []),
    ...(hasStructureSignal ? ["structure_engineer"] : []),
  ];
  const normalizedRecommended =
    recommendedExpertTypes.length > 0 ? recommendedExpertTypes : ["problem_guide"];
  const projectName = hasSmartSignal
    ? "ESP32 温湿度 MQTT 装置"
    : hasStructureSignal
      ? "ESP32 外壳 STL"
      : idea
        ? `${idea.slice(0, 18)}项目`
        : "新的创客项目";
  const requiresClarification = initialExpert === "problem_guide";
  const confidence = requiresClarification ? 0.4 : 0.82;
  const reason = requiresClarification
    ? "当前想法还比较宽泛，建议先由问题引导师帮助你进一步梳理。"
    : "根据创意内容推荐初始专家。";
  return {
    name: projectName,
    initialIdea: idea,
    recommendedExpertTypes: normalizedRecommended,
    availableExperts: expertDefinitions(),
    initialExpert,
    routerResult: {
      intent: requiresClarification ? "clarify_project_idea" : "technical_implementation",
      projectName,
      initialExpert,
      recommendedExperts: normalizedRecommended,
      confidence,
      reason,
      requiresClarification,
    },
    reason,
    confidence,
    requiresClarification,
  };
}

function expertDefinitions() {
  return [
    {
      id: "expert_def_problem_guide",
      type: "problem_guide",
      name: "问题引导师",
      description: "梳理问题、需求和项目方案",
      icon: "spark",
      builtIn: true,
      skillIds: ["idea-understanding"],
      supportedArtifactTypes: ["requirements"],
    },
    {
      id: "expert_def_smart_engineer",
      type: "smart_engineer",
      name: "智能工程师",
      description: "硬件、软件、IoT 和 AI 部署",
      icon: "cpu",
      builtIn: true,
      skillIds: ["hardware-selection"],
      supportedArtifactTypes: ["hardware_solution", "micropython_project"],
    },
    {
      id: "expert_def_structure_engineer",
      type: "structure_engineer",
      name: "结构工程师",
      description: "结构和外壳",
      icon: "box",
      builtIn: true,
      skillIds: ["parametric-modeling"],
      supportedArtifactTypes: ["cad_model"],
    },
  ];
}

function expertId(projectId: string, expertType = "problem_guide") {
  return `expert_${projectId}_${expertType}`;
}

function conversationId(projectId: string, expertType = "problem_guide") {
  return `conv_${projectId}_${expertType}`;
}

function packageRecord(id: string, status: string, zipBase64: string | null) {
  return {
    id,
    projectId: "prj_a",
    status,
    title: "测试项目包",
    fileName: `zhangwen-project-${id}.zip`,
    manifest: {
      schemaVersion: 1,
      packageId: id,
      packageVersion: 1,
      status,
      projectId: "prj_a",
      projectName: "项目甲",
      projectStage: "IDEA",
      exportedAt: "2026-07-08T00:00:00.000Z",
      itemKinds: ["MANIFEST", "PROJECT", "PRIVACY_REPORT"],
      artifactSelection: {
        includeDocuments: true,
        includeCode: true,
        includeCad: true,
        includeLessons: true,
        includeDeviceLogs: false,
      },
      artifacts: [],
      privacyReport: {
        ok: true,
        checks: [
          {
            dimension: "privacy-scan",
            severity: "PASS",
            message: "未发现敏感信息",
            path: null,
          },
        ],
      },
    },
    privacyReport: {
      ok: true,
      checks: [
        {
          dimension: "privacy-scan",
          severity: "PASS",
          message: "未发现敏感信息",
          path: null,
        },
      ],
    },
    artifactId: "artifact_package_prj_a",
    artifactVersionId: "artifact_package_prj_a_v1",
    zipBase64,
    createdAt: "2026-07-08T00:00:00.000Z",
    importedAt: status === "IMPORTED" ? "2026-07-08T00:00:00.000Z" : null,
  };
}

function projectName(projectId: string) {
  if (projectId === "prj_imported") return "导入项目";
  if (projectId === "prj_b") return "项目乙";
  if (projectId === "prj_new") return "新项目";
  return "项目甲";
}

function projectIdFromUrl(url: string) {
  const match = url.match(/\/api\/projects\/([^/]+)/);
  return match?.[1];
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function hardwareSkillSummary(
  skillName: string,
  componentId: string,
  displayName: string,
  category: "MCU" | "SENSOR",
  description: string,
) {
  return {
    skillName,
    componentId,
    displayName,
    description,
    category,
    status: "ACTIVE",
    sourceKind: "MIGRATED",
    revision: "skill-revision-1",
    verificationStatus: "VERIFIED",
    updatedAt: "2026-07-15T00:00:00Z",
    diagnostics: [],
  };
}

function hardwareComponent(
  id: string,
  name: string,
  category: "MCU" | "SENSOR",
  notes: string,
) {
  return {
    id,
    name,
    category,
    status: "ACTIVE",
    electrical: {
      voltage: 3.3,
      logicLevel: 3.3,
      peakCurrent: 0.2,
      communicationProtocol: category === "MCU" ? "GPIO" : "I2C",
      i2cAddress: category === "SENSOR" ? "0x76" : null,
      supportedMCUs: ["ESP32"],
      driverName: null,
      firmwareRequirement: null,
    },
    stock: 1,
    price: 0,
    ageRecommendation: null,
    safetyTags: ["低压"],
    notes,
    createdAt: "2026-07-14T00:00:00Z",
    updatedAt: "2026-07-14T00:00:00Z",
    skillName: category === "MCU" ? "esp32-devkit" : "bme280-sensor",
    skillRevision: "skill-revision-1",
    verificationStatus: "VERIFIED",
  };
}

function mechanicalProfileSummary() {
  return {
    profileId: "xiao_esp32s3",
    revision: "confirmed-v1",
    displayName: "XIAO ESP32S3",
    category: "mcu",
    dimensions: { length_x: 21, width_y: 17.8, height_z: 4.8 },
    mountingMode: "base_floor",
    mountingStrategy: "edge_retainer",
    preferredSurface: "base_floor",
    allowedSurfaces: ["base_floor"],
    clearance: 0.8,
    evidenceLevel: "TRUSTED",
    representation: "parametric_envelope",
    coordinateSystem: {
      origin: "envelope_center",
      x_axis: "length",
      y_axis: "width",
      positive_z: "height",
    },
    modelKind: "envelope",
    mountingHoles: [],
    openings: [],
    keepouts: [],
    contentSha256: "a".repeat(64),
    confirmedHardwareIds: [],
    lockedHardwareIds: [],
  };
}

function hardwareSkill(
  skillName: string,
  componentId: string,
  displayName: string,
  category: "MCU" | "SENSOR",
  description: string,
) {
  return {
    ...hardwareSkillSummary(skillName, componentId, displayName, category, description),
    files: [
      {
        path: "SKILL.md",
        title: "主 SKILL.md",
        kind: "entry",
        content: `# ${displayName}`,
        editable: true,
      },
      {
        path: "references/specifications.md",
        title: "技术规格",
        kind: "reference",
        content: "# 技术规格",
        editable: true,
      },
      {
        path: "references/compatibility-rules.md",
        title: "兼容规则",
        kind: "reference",
        content: "# 兼容规则",
        editable: true,
      },
    ],
    specification: {
      schema: "zhangwen.hardware-skill/v1",
      componentId,
      name: displayName,
      category,
      electrical: {
        voltage: 3.3,
        logicLevel: 3.3,
        peakCurrent: 0.2,
        communicationProtocol: category === "MCU" ? "GPIO" : "I2C",
        i2cAddress: category === "SENSOR" ? "0x76" : null,
        supportedMCUs: ["ESP32"],
        driverName: null,
        firmwareRequirement: null,
      },
      stock: 1,
      price: 0,
      ageRecommendation: null,
      safetyTags: ["低压"],
      notes: description,
      verificationStatus: "VERIFIED",
      sourceIds: [],
    },
    rules: [],
  };
}
