import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { afterEach, describe, it, expect, vi } from "vitest";
import { AppShell } from "../components/layout/AppShell";
import {
  createHostAdapter,
  HostAdapterProvider,
  platformCapabilities,
} from "../platform";

vi.mock("../components/floating/MonacoCodeEditor", () => ({
  default: ({
    filePath,
    value,
    onChange,
  }: {
    filePath: string;
    value: string;
    onChange: (value: string) => void;
  }) => (
    <textarea
      aria-label={`编辑 ${filePath}`}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

vi.mock("../hooks/useHealthCheck", () => ({
  useHealthCheck: () => ({ status: "ok" as const, version: "0.1.0" }),
}));

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("右侧 Tab 切换", () => {
  it("默认显示工作 Tab 内容", () => {
    render(<AppShell />);
    expect(screen.getByTestId("work-tab")).toBeInTheDocument();
  });

  it("普通模式按原型显示当前事项与精简就绪度，不呈现工程流水线", async () => {
    mockProposalFetch({ withPlan: true, manyArtifacts: true });
    render(<AppShell />);

    await screen.findAllByText("测试项目");
    const work = await screen.findByTestId("work-tab");
    expect(within(work).getByText("当前需要处理")).toBeInTheDocument();
    expect(within(work).getByRole("region", { name: "任务摘要" })).toBeInTheDocument();
    expect(within(work).queryByRole("checkbox", { name: "专业模式" })).not.toBeInTheDocument();
    expect(within(work).queryByText("工程详情")).not.toBeInTheDocument();
    expect(within(work).queryByRole("region", { name: "专家状态" })).not.toBeInTheDocument();
    expect(within(work).queryByRole("region", { name: "冲突与依赖" })).not.toBeInTheDocument();
    expect(within(work).queryByLabelText("项目流程状态")).not.toBeInTheDocument();
    expect(within(work).getByRole("region", { name: "MVP 交付就绪度" })).toBeInTheDocument();
    expect(within(work).queryByRole("region", { name: "工程流水线" })).not.toBeInTheDocument();
    expect(within(work).queryByRole("region", { name: "工程规格" })).not.toBeInTheDocument();
    expect(within(work).queryByRole("region", { name: "代码草稿" })).not.toBeInTheDocument();
    expect(within(work).queryByRole("region", { name: "结构件 CAD" })).not.toBeInTheDocument();
    expect(within(work).queryByRole("region", { name: "课程教案" })).not.toBeInTheDocument();
    expect(within(work).queryByText("推荐实现方案 · v3")).not.toBeInTheDocument();
  });

  it("中央确认与工作区共用一轮工程状态读取", async () => {
    const fetchMock = mockProposalFetch({ withPlan: true });
    render(<AppShell />);
    await screen.findAllByText("测试项目");

    const endpoints = [
      "/execution-plan/current",
      "/spec/current",
      "/code/current",
      "/cad/current",
      "/lesson/current",
    ];
    await waitFor(() => {
      endpoints.forEach((endpoint) => {
        expect(
          fetchMock.mock.calls.filter(([target]) => String(target).endsWith(endpoint)),
        ).toHaveLength(1);
      });
    });
  });

  it("工程状态读取异常会显式提示并提供重试", async () => {
    const fetchMock = mockProposalFetch();
    const fallback = fetchMock.getMockImplementation();
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/projects/prj_1/code/current")) {
        return json({
          detail: {
            code: "CODE_STATE_READ_FAILED",
            message: "代码状态暂时不可读。",
            retryable: true,
          },
        }, 503);
      }
      if (!fallback) throw new Error(`未处理的测试请求：${url}`);
      return fallback(input, init);
    });
    render(<AppShell />);

    expect((await screen.findAllByText(/工程状态读取失败/)).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: "重新读取" }).length).toBeGreaterThan(0);
  });

  it("执行计划确认只在中央主对话呈现", async () => {
    const fetchMock = mockProposalFetch({ withPlan: true, withPendingItems: false });
    render(<AppShell />);

    const confirmation = await screen.findByRole("region", { name: "待你确认" });
    expect(within(confirmation).getByText("执行计划")).toBeInTheDocument();
    fireEvent.click(within(confirmation).getByRole("button", { name: "确认继续" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/execution-plan/plan_1/approve"),
        expect.objectContaining({ method: "POST" })
      )
    );
    expect(screen.queryByRole("region", { name: "工作计划" })).not.toBeInTheDocument();
  });

  it("遗留 VALIDATED Spec 不再投影中央确认，也不自动生成代码", async () => {
    const fetchMock = mockProposalFetch({
      validatedSpec: true,
      withPendingItems: false,
    });
    render(<AppShell />);

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([target]) =>
        String(target).endsWith("/api/projects/prj_1/spec/current")
      )).toBe(true);
    });
    expect(screen.queryByRole("region", { name: "待你确认" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([target, init]) =>
      String(target).endsWith("/spec/confirm") && init?.method === "POST"
    )).toBe(false);
    expect(fetchMock.mock.calls.some(([target, init]) =>
      String(target).endsWith("/code/generate") && init?.method === "POST"
    )).toBe(false);
  });

  it("教案路线也不再显示 Spec 确认或自动生成教案", async () => {
    const fetchMock = mockProposalFetch({
      validatedSpec: true,
      withPendingItems: false,
      deliveryTrack: "lesson",
    });
    render(<AppShell />);

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([target]) =>
        String(target).endsWith("/api/projects/prj_1/spec/current")
      )).toBe(true);
    });
    expect(screen.queryByRole("region", { name: "待你确认" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([target, init]) =>
      String(target).endsWith("/spec/confirm") && init?.method === "POST"
    )).toBe(false);
    expect(fetchMock.mock.calls.some(([target, init]) =>
      String(target).endsWith("/lesson/generate") && init?.method === "POST"
    )).toBe(false);
  });

  it("专业模式显示 Skill 和模型路由摘要", async () => {
    mockProposalFetch({ withPlan: true });
    render(<AppShell />);

    expect(screen.queryByLabelText("当前模型")).not.toBeInTheDocument();
    const center = screen.getByTestId("center-chat");
    await enableProfessionalMode();
    await openIdeatorChat();
    fireEvent.click(await screen.findByText("工程详情"));

    expect(await screen.findByTestId("professional-panel")).toBeInTheDocument();
    expect(screen.getByLabelText("当前模型")).toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(center);
    expect(screen.getByText("2/3 启用")).toBeInTheDocument();
    expect(screen.getByText("deepseek · deepseek-v4-pro")).toBeInTheDocument();
  });

  it("工作 Tab 显示 MVP 交付就绪度并保留中央主对话", async () => {
    mockProposalFetch({ mvpReady: true });
    render(<AppShell />);

    await screen.findAllByText("测试项目");
    const center = screen.getByTestId("center-chat");
    await openEngineeringDetails();
    const readinessRegion = screen.getByRole("region", { name: "MVP 交付就绪度" });

    await within(readinessRegion).findByText("5 / 5");
    expect(within(readinessRegion).getByText("硬件核验 · 已就绪")).toBeInTheDocument();
    expect(within(readinessRegion).getByText("工程规格 · 已就绪")).toBeInTheDocument();
    expect(within(readinessRegion).getByText("代码 · 已就绪")).toBeInTheDocument();
    expect(within(readinessRegion).getByText("测试 · 已就绪")).toBeInTheDocument();
    expect(within(readinessRegion).getByText("设备部署 · 已就绪")).toBeInTheDocument();
    expect(within(readinessRegion).queryByText(/真实设备、真实 API Key/)).not.toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(center);
  });

  it("普通工作页不重复方案和产物，统一从产物 Tab 查看", async () => {
    mockProposalFetch({ manyArtifacts: true });
    render(<AppShell />);

    await screen.findAllByText("测试项目");
    const work = screen.getByTestId("work-tab");
    expect(within(work).queryByText("推荐实现方案 · v3")).not.toBeInTheDocument();
    expect(within(work).queryByText("最新产物")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "产物" }));
    expect(await screen.findByTestId("artifacts-tab")).toBeInTheDocument();
    expect(screen.getAllByText("推荐实现方案").length).toBeGreaterThan(0);
  });

  it("普通产物页提供类型和状态筛选，专业模式再显示专家与工程来源", async () => {
    mockProposalFetch({ manyArtifacts: true });
    render(<AppShell />);
    await screen.findAllByText("测试项目");

    fireEvent.click(screen.getByRole("tab", { name: "产物" }));
    const artifacts = await screen.findByTestId("artifacts-tab");
    expect(within(artifacts).getAllByRole("region", { name: "当前推荐方案" })).toHaveLength(1);
    expect(within(artifacts).getByLabelText("产物筛选")).toBeInTheDocument();
    expect(within(artifacts).getByLabelText("类型")).toBeInTheDocument();
    expect(within(artifacts).getByLabelText("状态")).toBeInTheDocument();
    expect(within(artifacts).queryByLabelText("专家")).not.toBeInTheDocument();
    expect(within(artifacts).queryByText(/所属专家：/)).not.toBeInTheDocument();
    expect(within(artifacts).queryByText("版本", { selector: "label" })).not.toBeInTheDocument();

    await enableProfessionalMode();
    expect(within(artifacts).getByLabelText("专家")).toBeInTheDocument();
    expect(within(artifacts).getAllByText(/所属专家：/).length).toBeGreaterThan(0);
  });

  it("切换和折叠右栏后保留产物筛选状态", async () => {
    mockProposalFetch({ manyArtifacts: true });
    render(<AppShell />);
    await screen.findAllByText("测试项目");

    fireEvent.click(screen.getByRole("tab", { name: "产物" }));
    const kindFilter = await screen.findByLabelText("类型");
    fireEvent.change(kindFilter, { target: { value: "CODE" } });
    expect(kindFilter).toHaveValue("CODE");

    fireEvent.click(screen.getByRole("tab", { name: "工作" }));
    fireEvent.click(screen.getByRole("button", { name: "收起右栏" }));
    fireEvent.click(screen.getByRole("button", { name: "展开右栏" }));
    fireEvent.click(screen.getByRole("tab", { name: "产物" }));

    expect(screen.getByLabelText("类型")).toHaveValue("CODE");
    expect(screen.getAllByTestId("center-chat")).toHaveLength(1);
  });

  it("工作 Tab 不再提供工程流水线生成按钮，中央主对话保持常驻", async () => {
    mockProposalFetch({ approvedSpec: true, withPendingItems: false });
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    const center = screen.getByTestId("center-chat");
    const work = screen.getByTestId("work-tab");

    expect(within(work).queryByRole("button", { name: "生成 Spec" })).not.toBeInTheDocument();
    expect(within(work).queryByRole("button", { name: "生成代码" })).not.toBeInTheDocument();
    expect(within(work).queryByRole("button", { name: "生成教案" })).not.toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(center);
  });

  it("点击产物 Tab 显示产物内容", () => {
    render(<AppShell />);
    fireEvent.click(screen.getByRole("tab", { name: "产物" }));
    expect(screen.getByTestId("artifacts-tab")).toBeInTheDocument();
  });

  it("点击设备 Tab 显示设备内容", () => {
    render(<AppShell />);
    fireEvent.click(screen.getByRole("tab", { name: "设备" }));
    expect(screen.getByTestId("devices-tab")).toBeInTheDocument();
  });

  it("设备 Tab 可以连接端口并启动受控代码上传，中央主对话保持常驻", async () => {
    const fetchMock = mockProposalFetch({ acceptedCode: true });
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    const center = screen.getByTestId("center-chat");
    await enableProfessionalMode();

    fireEvent.click(screen.getByRole("tab", { name: "设备" }));

    expect(await screen.findByText("Mock ESP32-S3 USB Serial")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "连接" }));
    const serialDevice = await screen.findByRole("region", { name: "串口设备" });
    expect(within(serialDevice).getByText("USB 串口 · 就绪")).toBeInTheDocument();
    expect(within(serialDevice).getByText("已连接")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "上传并运行" }));
    const resultRegion = await screen.findByRole("region", { name: "最近设备操作" });
    expect(resultRegion).toHaveTextContent("部署并启动完成");
    expect(resultRegion).toHaveTextContent("代码运行");
    expect(screen.getByText(/已同步到.*设备日志/)).toBeInTheDocument();

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/devices/deploy"),
        expect.objectContaining({ method: "POST" })
      )
    );
    const uploadCall = fetchMock.mock.calls.find(
      ([target, init]) => String(target).endsWith("/devices/deploy") && init?.method === "POST",
    );
    expect(JSON.parse(String(uploadCall?.[1]?.body))).toEqual(
      expect.objectContaining({
        channel: "USB_SERIAL",
        codeRunId: "code_1",
        sessionId: "device_session_1",
        dryRun: false,
        confirmWrite: true,
      }),
    );
    expect(screen.getByRole("region", { name: "固件烧录" })).toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(center);
  });

  it("普通设备页显示代码上传，专业模式才显示串口细节和固件高风险流程", async () => {
    mockProposalFetch({ acceptedCode: true });
    render(<AppShell />);
    await screen.findAllByText("测试项目");

    fireEvent.click(screen.getByRole("tab", { name: "设备" }));
    const devices = await screen.findByTestId("devices-tab");
    await within(devices).findByText("串口设备");
    expect(within(devices).queryByText("VID/PID")).not.toBeInTheDocument();
    expect(within(devices).queryByText("序列号")).not.toBeInTheDocument();
    expect(within(devices).getByRole("region", { name: "项目代码上传" })).toBeInTheDocument();
    expect(within(devices).getByRole("region", { name: "串口终端" })).toBeInTheDocument();
    expect(within(devices).getByRole("log")).toHaveTextContent("等待设备连接");
    expect(within(devices).queryByRole("region", { name: "固件烧录" })).not.toBeInTheDocument();
    expect(within(devices).queryByRole("region", { name: "设备日志" })).not.toBeInTheDocument();

    await enableProfessionalMode();
    expect(within(devices).getByText("VID/PID")).toBeInTheDocument();
    expect(within(devices).getByText("序列号")).toBeInTheDocument();
    expect(within(devices).getByRole("region", { name: "固件烧录" })).toHaveTextContent(
      "不会执行 Flash 擦除",
    );
  });

  it("固件烧录要求检查、明确地址、风险勾选和确认短语", async () => {
    const fetchMock = mockProposalFetch({ acceptedCode: true });
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    await enableProfessionalMode();
    fireEvent.click(screen.getByRole("tab", { name: "设备" }));
    await screen.findByText("Mock ESP32-S3 USB Serial");
    fireEvent.click(screen.getByRole("button", { name: "连接" }));
    const serialDevice = await screen.findByRole("region", { name: "串口设备" });
    expect(within(serialDevice).getByText("USB 串口 · 就绪")).toBeInTheDocument();

    const bytes = new Uint8Array([0xe9, 0, 0, 0]);
    const file = new File([bytes], "k10-micropython.bin", {
      type: "application/octet-stream",
    });
    Object.defineProperty(file, "arrayBuffer", {
      configurable: true,
      value: async () => bytes.buffer,
    });
    fireEvent.change(screen.getByLabelText("固件文件"), {
      target: { files: [file] },
    });

    const firmwareRegion = screen.getByRole("region", { name: "固件烧录" });
    expect(await within(firmwareRegion).findByText("ESP32-S3")).toBeInTheDocument();
    fireEvent.change(within(firmwareRegion).getByRole("textbox", { name: "写入地址" }), {
      target: { value: "0x0" },
    });
    fireEvent.click(within(firmwareRegion).getByRole("button", { name: "生成烧录计划" }));
    expect(await within(firmwareRegion).findByText(/将校验并写入/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: /板型、固件哈希/ }));
    fireEvent.change(screen.getByRole("textbox", { name: /输入.*烧录固件/ }), {
      target: { value: "烧录固件" },
    });
    fireEvent.click(screen.getByRole("button", { name: "烧录固件" }));

    await waitFor(() => {
      const flashCall = fetchMock.mock.calls.find(
        ([target, init]) => String(target).endsWith("/devices/flash") && init?.method === "POST",
      );
      expect(JSON.parse(String(flashCall?.[1]?.body))).toEqual(
        expect.objectContaining({
          dryRun: false,
          confirmFlash: true,
          confirmationPhrase: "烧录固件",
          address: 0,
        }),
      );
    });
  });

  it("普通协调器事项只保留在工作摘要，不抢占中央确认流", async () => {
    mockProposalFetch();
    render(<AppShell />);
    await screen.findAllByText("测试项目");

    await waitFor(() =>
      expect(screen.queryByRole("region", { name: "待你确认" })).not.toBeInTheDocument()
    );
    const workTab = screen.getByTestId("work-tab");
    expect(within(workTab).getByText("确认硬件方案")).toBeInTheDocument();
    const taskSummary = screen.getByRole("region", { name: "任务摘要" });
    expect(within(taskSummary).getByText("检查结构依赖")).toBeInTheDocument();
    expect(within(workTab).queryByText("请在中央主对话的“待你确认”卡片中处理。")).not.toBeInTheDocument();
    expect(within(workTab).queryByRole("button", { name: "确认方案" })).not.toBeInTheDocument();
  });

  it("与授权文案相同但没有服务端授权类型的事项不会进入中央确认", async () => {
    mockProposalFetch({ pendingMode: "spoofed" });
    render(<AppShell />);
    await screen.findAllByText("测试项目");

    expect(screen.queryByRole("region", { name: "待你确认" })).not.toBeInTheDocument();
    expect(within(screen.getByTestId("work-tab")).getByText("确认本地执行")).toBeInTheDocument();
  });

  it("普通协调器事项不会遮挡真实执行计划审批", async () => {
    mockProposalFetch({ withPlan: true });
    render(<AppShell />);

    await openEngineeringDetails();
    const confirmation = await screen.findByRole("region", { name: "待你确认" });
    expect(within(confirmation).getByText("执行计划")).toBeInTheDocument();
    expect(within(confirmation).queryByText("授权本地执行")).not.toBeInTheDocument();
    expect(within(confirmation).queryByText("确认硬件方案")).not.toBeInTheDocument();
  });

  it("桌面端确认本地 Skill 授权后在原回复显示真实执行动作", async () => {
    const fetchMock = mockProposalFetch({ pendingMode: "skill" });
    render(
      <HostAdapterProvider adapter={createHostAdapter(platformCapabilities("tauri"))}>
        <AppShell />
      </HostAdapterProvider>,
    );
    await screen.findAllByText("测试项目");

    const confirmation = await screen.findByRole("region", { name: "待你确认" });
    expect(within(confirmation).getByText("本地执行授权")).toBeInTheDocument();
    expect(within(confirmation).getByText("授权本地执行")).toBeInTheDocument();
    expect(within(confirmation).queryByText(/hardware-selection/)).not.toBeInTheDocument();
    fireEvent.click(within(confirmation).getByRole("button", { name: "确认授权" }));

    const center = within(screen.getByTestId("center-chat"));
    const progress = await center.findByRole("status", {
      name: "掌问执行进度",
    });
    expect(progress).not.toHaveTextContent("已确认本地执行授权");
    expect(progress).toHaveTextContent("正在执行本地工具");
    expect(center.getByText("准备执行已授权的本地检查。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "停止" })).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(
        ([target, init]) =>
          String(target).endsWith(
            "/api/projects/prj_1/pending-items/pending_current/resolve/stream",
          ) && init?.method === "POST",
      ),
    ).toBe(true);
    expect(
      fetchMock.mock.calls.some(([target]) =>
        String(target).endsWith(
          "/api/projects/prj_1/pending-items/pending_current/resolve",
        ),
      ),
    ).toBe(false);

    await waitFor(() =>
      expect(
        center.queryByRole("status", { name: "掌问执行进度" }),
      ).not.toBeInTheDocument(),
    );
    expect(center.getByText("准备执行已授权的本地检查。")).toBeInTheDocument();
  });

  it("停止已授权本地执行后刷新项目并清理原回复动作", async () => {
    const fetchMock = mockProposalFetch({
      pendingMode: "skill",
      keepPendingResolutionOpen: true,
    });
    render(
      <HostAdapterProvider adapter={createHostAdapter(platformCapabilities("tauri"))}>
        <AppShell />
      </HostAdapterProvider>,
    );
    await screen.findAllByText("测试项目");

    const centerElement = screen.getByTestId("center-chat");
    const confirmation = await screen.findByRole("region", { name: "待你确认" });
    fireEvent.click(within(confirmation).getByRole("button", { name: "确认授权" }));

    const center = within(centerElement);
    expect(
      await center.findByRole("status", { name: "掌问执行进度" }),
    ).toHaveTextContent("正在执行本地工具");
    fireEvent.click(screen.getByRole("button", { name: "停止" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining(
          "/api/projects/prj_1/chat/cancel/req_pending_resolution",
        ),
        expect.objectContaining({ method: "POST" }),
      ),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("region", { name: "待你确认" }),
      ).not.toBeInTheDocument(),
    );
    expect(
      center.queryByRole("status", { name: "掌问执行进度" }),
    ).not.toBeInTheDocument();
    expect(center.getByText("准备执行已授权的本地检查。")).toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(centerElement);
  });

  it("已授权本地执行失败后保留原回复并清理动作", async () => {
    mockProposalFetch({
      pendingMode: "skill",
      failPendingResolution: true,
    });
    render(
      <HostAdapterProvider adapter={createHostAdapter(platformCapabilities("tauri"))}>
        <AppShell />
      </HostAdapterProvider>,
    );
    await screen.findAllByText("测试项目");

    const center = within(screen.getByTestId("center-chat"));
    const confirmation = await screen.findByRole("region", { name: "待你确认" });
    fireEvent.click(within(confirmation).getByRole("button", { name: "确认授权" }));

    expect(
      await center.findByRole("status", { name: "掌问执行进度" }),
    ).toHaveTextContent("正在执行本地工具");
    await waitFor(() =>
      expect(
        center.queryByRole("status", { name: "掌问执行进度" }),
      ).not.toBeInTheDocument(),
    );
    expect(center.getByText("准备执行已授权的本地检查。")).toBeInTheDocument();
    expect(center.queryByText("受控本地工具执行失败，请重试。")).not.toBeInTheDocument();
  });

  it("浏览器模式保留本地授权确认点但禁止执行", async () => {
    mockProposalFetch({ pendingMode: "skill" });
    render(
      <HostAdapterProvider adapter={createHostAdapter(platformCapabilities("web"))}>
        <AppShell />
      </HostAdapterProvider>,
    );
    await screen.findAllByText("测试项目");

    const confirmation = await screen.findByRole("region", { name: "待你确认" });
    expect(
      within(confirmation).getByRole("button", { name: "确认授权" }),
    ).toBeDisabled();
    expect(
      within(confirmation).getByText(/当前浏览器模式不支持受控本地工具执行/),
    ).toBeInTheDocument();
    expect(
      within(confirmation).getByRole("button", { name: "暂不执行" }),
    ).not.toBeDisabled();
  });

  it("产物 Tab 显示领域状态、版本和过期原因", async () => {
    mockProposalFetch({ manyArtifacts: true });
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    await enableProfessionalMode();

    fireEvent.click(screen.getByRole("tab", { name: "产物" }));

    const artifactTab = screen.getByTestId("artifacts-tab");
    await waitFor(() =>
      expect(hasArtifactStatus(artifactTab, "待确认")).toBe(true)
    );
    const filters = within(artifactTab).getAllByRole("combobox");
    fireEvent.change(filters[0]!, { target: { value: "all" } });

    await waitFor(() =>
      expect(hasArtifactStatus(artifactTab, "已过期")).toBe(true)
    );
    expect(screen.getAllByText(/硬件方案 V2 已确认/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/proposal-agent/)).not.toBeInTheDocument();
  });

  it("设备控制不依赖当前聊天专家", async () => {
    mockProposalFetch({
      acceptedCode: true,
      activeExpertType: "structure_engineer",
    });
    render(<AppShell />);
    await screen.findAllByText("测试项目");

    fireEvent.click(screen.getByRole("tab", { name: "设备" }));

    expect(await screen.findByText("串口设备")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "连接" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "项目代码上传" })).toBeInTheDocument();
    expect(screen.queryByText(/设备控制需切换到智能工程师/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("checkbox", { name: "确认仅模拟固件烧录" })
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "固件 Dry Run" })).not.toBeInTheDocument();
  });

  it("切换 Tab 后中央主对话仍然存在", () => {
    render(<AppShell />);
    const chatBefore = screen.getByTestId("center-chat");
    expect(chatBefore).toBeInTheDocument();

    // 切换到产物
    fireEvent.click(screen.getByRole("tab", { name: "产物" }));
    expect(screen.getByTestId("center-chat")).toBeInTheDocument();

    // 切换到设备
    fireEvent.click(screen.getByRole("tab", { name: "设备" }));
    expect(screen.getByTestId("center-chat")).toBeInTheDocument();

    // 切换回工作
    fireEvent.click(screen.getByRole("tab", { name: "工作" }));
    expect(screen.getByTestId("center-chat")).toBeInTheDocument();
  });

  it("切换 Tab 和浮窗操作后中央主对话没有重复实例", async () => {
    mockProposalFetch();
    render(<AppShell />);
    await screen.findAllByText("测试项目");

    expect(screen.getAllByTestId("center-chat")).toHaveLength(1);

    fireEvent.click(screen.getByRole("tab", { name: "产物" }));
    fireEvent.click(await findFirstArtifactOpenButton());
    expect(screen.getAllByTestId("center-chat")).toHaveLength(1);

    fireEvent.click(screen.getByLabelText("关闭浮窗"));
    fireEvent.click(screen.getByRole("tab", { name: "设备" }));
    await screen.findByText("串口设备");
    expect(screen.getAllByTestId("center-chat")).toHaveLength(1);
  });
});

describe("简化工作台入口", () => {
  it("顶栏和左栏均提供新建入口，左栏承载项目列表", async () => {
    mockProposalFetch();
    render(<AppShell />);
    await screen.findAllByText("测试项目");

    const topBar = screen.getByRole("banner");
    expect(within(topBar).getByLabelText("切换项目")).toBeInTheDocument();
    expect(within(topBar).getByRole("button", { name: "新建项目" })).toBeInTheDocument();
    expect(within(topBar).getByRole("button", { name: "项目工具" })).toBeInTheDocument();

    const left = screen.getByTestId("left-sidebar");
    expect(within(left).getByRole("button", { name: "新建项目" })).toBeInTheDocument();
    expect(within(left).getByRole("list", { name: "项目列表" })).toBeInTheDocument();
    expect(within(left).getByText("项目资源")).toBeInTheDocument();
    expect(within(left).queryByLabelText("新项目创意")).not.toBeInTheDocument();
    expect(within(left).queryByText("最近项目")).not.toBeInTheDocument();
    expect(within(left).queryByText("模板")).not.toBeInTheDocument();
    expect(within(left).queryByText("项目包")).not.toBeInTheDocument();
    expect(within(left).queryByText("硬件库")).not.toBeInTheDocument();
  });

  it("新建项目和项目工具覆盖层不卸载中央主对话", async () => {
    mockProposalFetch();
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    const center = screen.getByTestId("center-chat");

    fireEvent.click(
      within(screen.getByRole("banner")).getByRole("button", { name: "新建项目" }),
    );
    const createDialog = screen.getByRole("dialog", { name: "新建项目" });
    expect(within(createDialog).getByLabelText("新项目创意")).toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(center);
    fireEvent.click(within(createDialog).getByRole("button", { name: "关闭新建项目" }));

    fireEvent.click(screen.getByRole("button", { name: "项目工具" }));
    const toolsDialog = screen.getByRole("dialog", { name: "项目工具" });
    expect(within(toolsDialog).getByRole("button", { name: "重命名项目" })).toBeInTheDocument();
    expect(within(toolsDialog).getByRole("button", { name: "归档项目" })).toBeInTheDocument();
    expect(within(toolsDialog).getByText("项目包")).toBeInTheDocument();
    expect(within(toolsDialog).getByRole("region", { name: "硬件库" })).toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(center);
  });

  it("专业模式显示项目专家胶囊且中央只有一个对话", async () => {
    mockProposalFetch();
    render(<AppShell />);
    await screen.findAllByText("测试项目");

    await enableProfessionalMode();
    await openIdeatorChat();
    const strip = screen.getByRole("group", { name: "项目智能体" });
    expect(within(strip).getByRole("button", { name: /智能工程师/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByTestId("center-chat")).toHaveLength(1);
  });
});

describe("草稿保留", () => {
  it("窗口缩至窄屏时收起两侧栏，且左右抽屉互斥", async () => {
    let narrow = false;
    vi.stubGlobal("matchMedia", vi.fn().mockImplementation((query: string) => ({
      matches: query === "(max-width: 720px)" && narrow,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })));
    mockProposalFetch();
    render(<AppShell />);
    await screen.findAllByText("测试项目");

    expect(screen.getByRole("button", { name: "折叠侧栏" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "收起右栏" })).toBeInTheDocument();

    narrow = true;
    fireEvent(window, new Event("resize"));
    expect(screen.getByRole("button", { name: "展开侧栏" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "展开右栏" })).toBeInTheDocument();
    expect(screen.getAllByTestId("center-chat")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "展开侧栏" }));
    expect(screen.getByRole("button", { name: "折叠侧栏" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "展开右栏" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "关闭项目抽屉" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "关闭打开的抽屉" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "关闭打开的抽屉" }));
    expect(screen.getByRole("button", { name: "展开侧栏" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "展开右栏" }));
    expect(screen.getByRole("button", { name: "展开侧栏" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "收起右栏" })).toBeInTheDocument();
    expect(screen.getAllByTestId("center-chat")).toHaveLength(1);
  });

  it("折叠和展开右栏后中央主对话与草稿保持", async () => {
    mockProposalFetch();
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    const center = screen.getByTestId("center-chat");
    const textarea = screen.getByPlaceholderText("描述你想做的作品…");
    fireEvent.change(textarea, { target: { value: "右栏折叠测试草稿" } });

    fireEvent.click(screen.getByRole("button", { name: "收起右栏" }));
    expect(screen.getByRole("button", { name: "展开右栏" })).toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(center);
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue(
      "右栏折叠测试草稿"
    );

    fireEvent.click(screen.getByRole("button", { name: "展开右栏" }));
    expect(screen.getByRole("tab", { name: "工作" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "产物" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "设备" })).toBeInTheDocument();
    expect(screen.getByTestId("center-chat")).toBe(center);
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue(
      "右栏折叠测试草稿"
    );
  });

  it("切换 Tab 后输入框草稿保留", async () => {
    mockProposalFetch();
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    const textarea = screen.getByPlaceholderText("描述你想做的作品…");

    // 输入草稿
    fireEvent.change(textarea, { target: { value: "我的草稿内容" } });
    expect(textarea).toHaveValue("我的草稿内容");

    // 切换 Tab
    fireEvent.click(screen.getByRole("tab", { name: "产物" }));
    fireEvent.click(screen.getByRole("tab", { name: "设备" }));
    fireEvent.click(screen.getByRole("tab", { name: "工作" }));

    // 草稿仍在
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue(
      "我的草稿内容"
    );
  });

  it("打开/关闭浮窗后草稿保留", async () => {
    mockProposalFetch();
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    const textarea = screen.getByPlaceholderText("描述你想做的作品…");

    // 输入草稿
    fireEvent.change(textarea, { target: { value: "浮窗测试草稿" } });

    // 切换到产物 Tab
    fireEvent.click(screen.getByRole("tab", { name: "产物" }));

    // 打开浮窗
    fireEvent.click(await findFirstArtifactOpenButton());
    expect(screen.getByTestId("floating-window")).toBeInTheDocument();

    // 草稿仍在
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue(
      "浮窗测试草稿"
    );

    // 关闭浮窗
    fireEvent.click(screen.getByLabelText("关闭浮窗"));
    expect(screen.queryByTestId("floating-window")).not.toBeInTheDocument();

    // 草稿仍在
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue(
      "浮窗测试草稿"
    );
  });
});

describe("浮窗", () => {
  it("窄屏打开浮窗时收起右栏并保留中央草稿", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockImplementation((query: string) => ({
      matches: query === "(max-width: 720px)",
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })));
    mockProposalFetch();
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    const center = screen.getByTestId("center-chat");
    const textarea = screen.getByPlaceholderText("描述你想做的作品…");
    fireEvent.change(textarea, { target: { value: "窄屏浮窗草稿" } });

    fireEvent.click(screen.getByRole("button", { name: "展开右栏" }));
    fireEvent.click(screen.getByRole("tab", { name: "产物" }));
    await openArtifactFloatingByTitle("项目立项书");

    expect(screen.getByTestId("floating-window")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "展开右栏" })).toBeInTheDocument();
    expect(screen.getAllByTestId("center-chat")).toHaveLength(1);
    expect(screen.getByTestId("center-chat")).toBe(center);
    expect(screen.getByPlaceholderText("描述你想做的作品…")).toHaveValue(
      "窄屏浮窗草稿",
    );
  });

  it("从已确认 v2 保存 v3 后按版本状态分组且中央主对话保持单一挂载", async () => {
    const fetchMock = mockProposalFetch({ editableCodeArtifact: true });
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    const center = screen.getByTestId("center-chat");

    await enableProfessionalMode();
    fireEvent.click(screen.getByRole("tab", { name: "产物" }));
    await openArtifactFloatingByTitle("MicroPython 代码");
    const editor = await screen.findByRole("textbox", { name: "编辑 src/main.py" });
    fireEvent.change(editor, { target: { value: "print('用户保存 v3')\n" } });
    fireEvent.change(screen.getByRole("textbox", { name: "变更摘要" }), {
      target: { value: "更新主循环" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存新版本" }));

    await waitFor(() =>
      expect(screen.getByText("MicroPython 代码 v3", { selector: ".floating-title" }))
        .toBeInTheDocument(),
    );
    await waitFor(() => {
      const artifactTab = screen.getByTestId("artifacts-tab");
      const reviewGroup = within(artifactTab).getByRole("region", { name: "待确认" });
      const approvedGroup = within(artifactTab).getByRole("region", { name: "已确认" });
      expect(within(reviewGroup).getByText("MicroPython 代码")).toBeInTheDocument();
      expect(within(reviewGroup).getByText("v3")).toBeInTheDocument();
      expect(within(reviewGroup).queryByText("v2")).not.toBeInTheDocument();
      expect(within(approvedGroup).getByText("MicroPython 代码")).toBeInTheDocument();
      expect(within(approvedGroup).getByText("v2")).toBeInTheDocument();
      expect(within(approvedGroup).queryByText("v3")).not.toBeInTheDocument();
    });
    expect(screen.getAllByTestId("center-chat")).toHaveLength(1);
    expect(screen.getByTestId("center-chat")).toBe(center);
    expect(screen.getAllByRole("tab", { name: /^(工作|产物|设备)$/ })).toHaveLength(3);
    expect(fetchMock.mock.calls.some(([target, init]) =>
      String(target).endsWith("/api/projects/prj_1/code/code_2") && init?.method === "PUT"
    )).toBe(true);
  });

  it("可以通过产物 Tab 打开浮窗", async () => {
    mockProposalFetch();
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    fireEvent.click(screen.getByRole("tab", { name: "产物" }));

    await openArtifactFloatingByTitle("项目立项书");

    const floating = screen.getByTestId("floating-window");
    expect(floating).toBeInTheDocument();
    expect(within(floating).getByRole("table", { name: "项目立项表" }))
      .toBeInTheDocument();
    expect(within(floating).getByText("项目目标")).toBeInTheDocument();
  });

  it("浮窗可以关闭并保留再次打开状态", async () => {
    mockProposalFetch();
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    fireEvent.click(screen.getByRole("tab", { name: "产物" }));

    await openArtifactFloatingByTitle("项目立项书");
    expect(screen.getByTestId("floating-window")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("关闭浮窗"));
    expect(screen.queryByTestId("floating-window")).not.toBeInTheDocument();

    await openArtifactFloatingByTitle("项目立项书");
    const floating = screen.getByTestId("floating-window");
    expect(floating).toBeInTheDocument();
    expect(within(floating).getByText("项目目标")).toBeInTheDocument();
  });

  it("打开浮窗不改变中央主对话", async () => {
    mockProposalFetch();
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    const chatMessages = screen.getByTestId("chat-messages");
    const messagesBefore = chatMessages.textContent;

    fireEvent.click(screen.getByRole("tab", { name: "产物" }));
    fireEvent.click(await findFirstArtifactOpenButton());

    // 中央对话内容不变
    expect(screen.getByTestId("chat-messages").textContent).toBe(
      messagesBefore
    );
  });

  it("重复打开同一产物版本只保留一个浮窗", async () => {
    mockProposalFetch();
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    fireEvent.click(screen.getByRole("tab", { name: "产物" }));

    const openButton = await findFirstArtifactOpenButton();
    fireEvent.click(openButton);
    fireEvent.click(openButton);

    expect(screen.getAllByTestId("floating-window")).toHaveLength(1);
  });

  it("最多同时显示三个浮窗", async () => {
    mockProposalFetch({ manyArtifacts: true });
    render(<AppShell />);
    await screen.findAllByText("测试项目");
    fireEvent.click(screen.getByRole("tab", { name: "产物" }));

    const buttons = await screen.findAllByText("完整查看");
    for (const button of buttons) {
      fireEvent.click(button);
    }

    expect(screen.getAllByTestId("floating-window")).toHaveLength(3);
  });
});

async function openEngineeringDetails() {
  await enableProfessionalMode();
  const summary = await screen.findByText("工程详情");
  fireEvent.click(summary);
}

async function enableProfessionalMode() {
  if (screen.queryByText("工程详情")) return;
  fireEvent.click(screen.getByRole("button", { name: "打开设置" }));
  const settings = screen.getByRole("dialog", { name: "设置" });
  const professionalMode = within(settings).getByRole("checkbox", {
    name: "专业模式",
  });
  if (!(professionalMode as HTMLInputElement).checked) {
    fireEvent.click(professionalMode);
  }
  fireEvent.click(within(settings).getByRole("button", { name: "关闭设置" }));
}

async function openIdeatorChat() {
  const strip = await screen.findByRole("group", { name: "项目智能体" });
  fireEvent.click(within(strip).getByRole("button", { name: /智能工程师/ }));
}

async function openArtifactFloatingByTitle(title: string) {
  const titleNode = await screen.findByText(title, { selector: ".artifact-title" });
  const card = titleNode.closest(".artifact-card");
  if (!card) {
    throw new Error(`Artifact card not found: ${title}`);
  }
  fireEvent.click(within(card as HTMLElement).getByRole("button", { name: "完整查看" }));
}

async function findFirstArtifactOpenButton() {
  const buttons = await screen.findAllByText("完整查看");
  const button = buttons[0];
  if (!button) {
    throw new Error("Artifact open button not found");
  }
  return button;
}

function hasArtifactStatus(container: HTMLElement, label: string) {
  return Array.from(container.querySelectorAll(".artifact-status")).some(
    (item) => item.textContent === label
  );
}

function mockProposalFetch({
  withPlan = false,
  manyArtifacts = false,
  approvedSpec = false,
  validatedSpec = false,
  acceptedCode = false,
  editableCodeArtifact = false,
  mvpReady = false,
  withPendingItems = true,
  pendingMode = "project",
  keepPendingResolutionOpen = false,
  failPendingResolution = false,
  activeExpertType = "smart_engineer",
  deliveryTrack = "project",
}: {
  withPlan?: boolean;
  manyArtifacts?: boolean;
  approvedSpec?: boolean;
  validatedSpec?: boolean;
  acceptedCode?: boolean;
  editableCodeArtifact?: boolean;
  mvpReady?: boolean;
  withPendingItems?: boolean;
  pendingMode?: "project" | "skill" | "spoofed";
  keepPendingResolutionOpen?: boolean;
  failPendingResolution?: boolean;
  activeExpertType?: "problem_guide" | "smart_engineer" | "structure_engineer";
  deliveryTrack?: "project" | "lesson";
} = {}) {
  let plan = executionPlan("AWAITING_APPROVAL");
  let currentSpec: ReturnType<typeof specRun> | null = approvedSpec
    ? specRun("APPROVED")
    : validatedSpec
      ? specRun("VALIDATED")
      : null;
  const initialEditableCode = editableCodeRun({
    id: "code_2",
    version: 2,
    status: "ACCEPTED",
  });
  let currentCode: ReturnType<typeof codeRun> | ReturnType<typeof editableCodeRun> | null =
    editableCodeArtifact
      ? initialEditableCode
      : acceptedCode
        ? codeRun("ACCEPTED")
        : null;
  let currentCodeArtifact = editableCodeArtifact
    ? codeArtifact(initialEditableCode)
    : null;
  let currentLesson: ReturnType<typeof lessonRun> | null = null;
  let currentSession: ReturnType<typeof deviceSession> | null = null;
  let currentPendingResolved = false;
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

    if (url.endsWith("/api/skills") && method === "GET") {
      return json({
        skills: [
          skill("skill_project_reader", true, ["READ_PROJECT"]),
          skill("skill_model_draft", true, ["RUN_MODEL"]),
          skill("skill_shell_user", false, ["RUN_SHELL"]),
        ],
      });
    }

    if (url.endsWith("/api/model-router/route") && method === "POST") {
      return json({
        route: {
          provider: "deepseek",
          model: "deepseek-v4-pro",
          strategy: "BALANCED",
          retryCount: 1,
          fallbackModel: "deepseek-v4-flash",
          costTier: "MEDIUM",
          qualityTier: "HIGH",
          reasoning: "测试路由",
        },
      });
    }

    if (
      (url.endsWith("/api/projects") ||
        url.endsWith("/api/projects?includeArchived=true")) &&
      method === "GET"
    ) {
      return json({
        activeProjectId: "prj_1",
        projects: [
          {
            id: "prj_1",
            name: "测试项目",
            stage: "PROPOSAL_DRAFT",
            activeExpertIds: [expertId(activeExpertType)],
            selectedModel: "deepseek-v4-flash",
            messageCount: 0,
            draftUpdatedAt: null,
            archivedAt: null,
            updatedAt: "2026-07-08T00:00:00.000Z",
            lastOpenedAt: "2026-07-08T00:00:00.000Z",
          },
        ],
      });
    }

    if (url.endsWith("/api/projects/prj_1/solution/current") && method === "GET") {
      return json({ solution: solution() });
    }

    if (url.endsWith("/api/projects/prj_1/artifacts") && method === "GET") {
      return json({
        artifacts: currentCodeArtifact
          ? [solutionArtifact(), currentCodeArtifact]
          : manyArtifacts
            ? [solutionArtifact(), artifact("artifact_1", "项目立项书"), artifact("artifact_2", "代码草稿"), artifact("artifact_3", "结构预览"), artifact("artifact_4", "设备日志")]
            : [solutionArtifact(), artifact("artifact_1", "项目立项书")],
      });
    }

    if (url.endsWith("/api/projects/prj_1/artifacts/artifact_solution_prj_1") && method === "GET") {
      return json({ artifact: solutionArtifact() });
    }

    if (url.endsWith("/api/projects/prj_1/artifacts/artifact_code_prj_1") && method === "GET") {
      return currentCodeArtifact
        ? json({ artifact: currentCodeArtifact })
        : json({ code: "ARTIFACT_NOT_FOUND" }, 404);
    }

    if (url.endsWith("/api/projects/prj_1/mvp/readiness") && method === "GET") {
      return json({ readiness: readinessReport(mvpReady ? "READY" : "NEEDS_ACTION") });
    }

    if (url.endsWith("/api/projects/prj_1/progress") && method === "GET") {
      const readiness = readinessReport(mvpReady ? "READY" : "NEEDS_ACTION");
      const status = mvpReady ? "READY" : "NEEDS_ACTION";
      const currentActionTitle =
        !withPendingItems || currentPendingResolved
          ? "继续推进当前项目"
          : pendingMode === "project"
            ? "确认硬件方案"
            : pendingMode === "spoofed"
              ? "确认本地执行"
              : "授权本地执行";
      return json({
        progress: {
          projectId: "prj_1",
          revision: 1,
          stage: "PROPOSAL_DRAFT",
          stageLabel: "立项规划",
          status,
          currentAction: {
            id: "continue",
            title: currentActionTitle,
            description: "请在中央对话确认下一步。",
            blocking: false,
          },
          readiness,
          readinessSummary: [
            progressDimension("HARDWARE", "硬件核验", status),
            progressDimension("SPECIFICATION", "工程规格", status),
            progressDimension("CODE", "代码", status),
            progressDimension("TESTING", "测试", status),
            progressDimension("DEPLOYMENT", "设备部署", status),
          ],
          artifacts: { draftCount: 0, formalCount: 2, message: "已有正式产物。" },
          consistency: "CONSISTENT",
          consistencyMessages: [],
        },
      });
    }

    if (url.endsWith("/api/projects/prj_1/spec/current") && method === "GET") {
      return currentSpec ? json({ spec: currentSpec }) : json({ code: "SPEC_NOT_FOUND" }, 404);
    }

    if (url.endsWith("/api/projects/prj_1/proposal/current") && method === "GET") {
      return json({ proposal: proposal() });
    }

    if (url.endsWith("/api/projects/prj_1/spec/generate") && method === "POST") {
      currentSpec = specRun("VALIDATED");
      return json({ spec: currentSpec });
    }

    if (url.endsWith("/api/projects/prj_1/spec/confirm") && method === "POST") {
      currentSpec = specRun("APPROVED");
      return json({ spec: currentSpec });
    }

    if (url.endsWith("/api/projects/prj_1/spec/reject") && method === "POST") {
      currentSpec = specRun("REJECTED");
      return json({ spec: currentSpec });
    }

    if (url.endsWith("/api/projects/prj_1/code/current") && method === "GET") {
      return currentCode ? json({ codeRun: currentCode }) : json({ code: "CODE_NOT_FOUND" }, 404);
    }

    if (/\/api\/projects\/prj_1\/code\/code_\d+$/.test(url) && method === "GET") {
      return currentCode ? json({ codeRun: currentCode }) : json({ code: "CODE_NOT_FOUND" }, 404);
    }

    if (/\/api\/projects\/prj_1\/code\/code_\d+$/.test(url) && method === "PUT") {
      const request = JSON.parse(String(init?.body ?? "{}"));
      const previousVersions = currentCodeArtifact?.versions ?? [];
      const nextVersion = (currentCode?.version ?? 0) + 1;
      currentCode = editableCodeRun({
        id: `code_${nextVersion}`,
        version: nextVersion,
        mainContent: request.files?.find((file: { path: string }) => file.path === "src/main.py")?.content,
        summary: request.summary,
        baseSnapshotId: request.baseCodeRunId,
      });
      currentCodeArtifact = codeArtifact(currentCode, previousVersions);
      return json({ codeRun: currentCode });
    }

    if (url.endsWith("/api/projects/prj_1/code/generate") && method === "POST") {
      currentCode = editableCodeRun({ status: "READY_FOR_REVIEW" });
      currentCodeArtifact = codeArtifact(currentCode);
      return json({ codeRun: currentCode });
    }

    if (url.endsWith("/api/projects/prj_1/code/accept") && method === "POST") {
      currentCode = codeRun("ACCEPTED");
      return json({ codeRun: currentCode });
    }

    if (url.endsWith("/api/projects/prj_1/code/reject") && method === "POST") {
      currentCode = codeRun("REJECTED");
      return json({ codeRun: currentCode });
    }

    if (url.endsWith("/api/projects/prj_1/code/rollback") && method === "POST") {
      currentCode = codeRun("ROLLED_BACK");
      return json({ codeRun: currentCode });
    }

    if (url.endsWith("/api/projects/prj_1/lesson/current") && method === "GET") {
      return currentLesson ? json({ lessonRun: currentLesson }) : json({ code: "LESSON_NOT_FOUND" }, 404);
    }

    if (url.endsWith("/api/projects/prj_1/lesson/generate") && method === "POST") {
      currentLesson = lessonRun("READY_FOR_REVIEW");
      return json({ lessonRun: currentLesson });
    }

    if (url.endsWith("/api/projects/prj_1/lesson/confirm") && method === "POST") {
      currentLesson = lessonRun("APPROVED");
      return json({ lessonRun: currentLesson });
    }

    if (url.endsWith("/api/projects/prj_1/lesson/reject") && method === "POST") {
      currentLesson = lessonRun("REJECTED");
      return json({ lessonRun: currentLesson });
    }

    if (url.endsWith("/api/projects/prj_1/devices/ports") && method === "GET") {
      return json({
        ports: [
          {
            id: "mock_port_esp32_s3",
            label: "Mock ESP32-S3 USB Serial",
            transport: "mock-usb-serial",
            chip: "ESP32-S3",
            serialNumber: null,
            available: true,
          },
        ],
      });
    }

    if (url.endsWith("/api/projects/prj_1/devices/session/current") && method === "GET") {
      return currentSession ? json({ session: currentSession }) : json({ code: "DEVICE_SESSION_NOT_FOUND" }, 404);
    }

    if (url.endsWith("/api/projects/prj_1/devices/connect") && method === "POST") {
      currentSession = deviceSession();
      return json({ session: currentSession });
    }

    if (url.endsWith("/api/projects/prj_1/devices/deploy") && method === "POST") {
      const request = JSON.parse(String(init?.body ?? "{}")) as {
        operationId: string;
        channel: string;
        codeRunId: string;
        sessionId: string;
      };
      const baseOperation = deviceOperation("UPLOAD_CODE", "COMPLETED", false);
      const operation = {
        ...baseOperation,
        id: request.operationId,
        metadata: {
          ...baseOperation.metadata,
          channel: request.channel,
          codeRunId: request.codeRunId,
          targetId: request.sessionId,
        },
      };
      currentSession = deviceSession([
        logEntry("log_1", "INFO", "已建立 Mock MicroPython 会话，未访问真实串口。"),
        logEntry("log_2", "INFO", "MicroPython 上传 Dry Run 完成：5 个文件。"),
      ]);
      return json({ operation, session: currentSession });
    }

    if (url.endsWith("/api/projects/prj_1/devices/firmware/inspect") && method === "POST") {
      return json({ candidate: firmwareCandidate() });
    }

    if (url.endsWith("/api/projects/prj_1/devices/firmware/prepare") && method === "POST") {
      return json({
        plan: {
          candidate: firmwareCandidate(),
          sessionId: "device_session_1",
          address: 0,
          confirmationToken: "firmware-confirmation-token",
          expiresAt: "2026-07-08T00:03:00.000Z",
          summary: "将校验并写入 k10-micropython.bin；不执行 Flash 擦除。",
        },
      });
    }

    if (url.endsWith("/api/projects/prj_1/devices/flash") && method === "POST") {
      const operation = deviceOperation("FLASH_FIRMWARE", "COMPLETED", false);
      currentSession = deviceSession([
        logEntry("log_1", "INFO", "已建立 Mock MicroPython 会话，未访问真实串口。"),
        logEntry("log_3", "WARNING", "固件烧录仅完成 Dry Run；真实 Flash 操作需要外部人工确认。"),
      ]);
      return json({ operation, session: currentSession });
    }

    if (url.endsWith("/api/projects/prj_1/execution-plan/current") && method === "GET") {
      return withPlan ? json({ plan }) : json({ code: "EXECUTION_PLAN_NOT_FOUND" }, 404);
    }

    if (url.endsWith("/api/projects/prj_1/execution-plan/plan_1/approve") && method === "POST") {
      plan = executionPlan("COMPLETED");
      return json({ plan });
    }

    if (url.endsWith("/api/projects/prj_1/draft") && method === "PUT") {
      const body = JSON.parse(String(init?.body ?? "{}"));
      return json({ workspace: workspace(body.content ?? "", activeExpertType, currentPendingResolved, withPendingItems, pendingMode, deliveryTrack) });
    }

    if (url.endsWith(`/api/projects/prj_1/experts/${expertId(activeExpertType)}/activate`) && method === "POST") {
      return json({ workspace: workspace("", activeExpertType, currentPendingResolved, withPendingItems, pendingMode, deliveryTrack) });
    }

    if (url.endsWith("/api/projects/prj_1/pending-items/pending_current/resolve") && method === "POST") {
      currentPendingResolved = true;
      return json({ workspace: workspace("", activeExpertType, currentPendingResolved, withPendingItems, pendingMode, deliveryTrack) });
    }

    if (
      url.endsWith(
        "/api/projects/prj_1/pending-items/pending_current/resolve/stream",
      ) && method === "POST"
    ) {
      currentPendingResolved = true;
      return pendingResolutionStream(
        activeExpertType,
        keepPendingResolutionOpen,
        failPendingResolution,
        init?.signal,
      );
    }

    if (
      url.endsWith(
        "/api/projects/prj_1/chat/cancel/req_pending_resolution",
      ) && method === "POST"
    ) {
      return json({ requestId: "req_pending_resolution", canceled: true });
    }

    if (url.endsWith("/api/projects/prj_1/pending-items/pending_current/dismiss") && method === "POST") {
      currentPendingResolved = true;
      return json({ workspace: workspace("", activeExpertType, currentPendingResolved, withPendingItems, pendingMode, deliveryTrack) });
    }

    if (url.endsWith("/api/projects/prj_1") && method === "GET") {
      return json({ workspace: workspace("", activeExpertType, currentPendingResolved, withPendingItems, pendingMode, deliveryTrack) });
    }

    return json({}, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function executionPlan(status: "AWAITING_APPROVAL" | "COMPLETED") {
  const nodeStatus = status === "COMPLETED" ? "COMPLETED" : "AWAITING_APPROVAL";
  return {
    id: "plan_1",
    projectId: "prj_1",
    proposalId: "prop_1",
    status,
    createdAt: "2026-07-08T00:00:00.000Z",
    updatedAt: "2026-07-08T00:00:00.000Z",
    startedAt: "2026-07-08T00:00:00.000Z",
    completedAt: status === "COMPLETED" ? "2026-07-08T00:00:01.000Z" : null,
    nodes: [
      {
        id: "node_review",
        planId: "plan_1",
        projectId: "prj_1",
        agentId: "orchestrator",
        title: "确认工程规格",
        description: "等待用户确认。",
        status: nodeStatus,
        dependencies: [],
        attempts: 0,
        maxAttempts: 2,
        requiresApproval: true,
        logs: [],
        createdAt: "2026-07-08T00:00:00.000Z",
        updatedAt: "2026-07-08T00:00:00.000Z",
        startedAt: null,
        completedAt: status === "COMPLETED" ? "2026-07-08T00:00:01.000Z" : null,
        error: null,
      },
    ],
  };
}

function skill(id: string, enabled: boolean, permissions: string[]) {
  return {
    id,
    name: id,
    description: "测试 Skill",
    origin: id.includes("user") ? "USER" : "BUILT_IN",
    enabled,
    inputSchema: { type: "object" },
    outputSchema: { type: "object" },
    permissions,
    createdAt: "2026-07-08T00:00:00.000Z",
    updatedAt: "2026-07-08T00:00:00.000Z",
  };
}

function expertId(
  expertType: "problem_guide" | "smart_engineer" | "structure_engineer" = "smart_engineer"
) {
  return `expert_prj_1_${expertType}`;
}

function conversationId(
  expertType: "problem_guide" | "smart_engineer" | "structure_engineer" = "smart_engineer"
) {
  return `conv_prj_1_${expertType}`;
}

function expertLabel(
  expertType: "problem_guide" | "smart_engineer" | "structure_engineer"
) {
  return expertDefinitions().find((definition) => definition.type === expertType)?.name ?? expertType;
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

function pendingItem(
  id: "pending_current" | "pending_next",
  highlighted: boolean,
  pendingMode: "project" | "skill" | "spoofed" = "project",
) {
  const isCurrent = id === "pending_current";
  if (isCurrent && (pendingMode === "skill" || pendingMode === "spoofed")) {
    return {
      id,
      projectId: "prj_1",
      title: "确认本地执行",
      description: "该操作可能产生本地或外部影响，确认后才能执行。",
      priority: "confirmation",
      reason: "本地执行需要用户明确授权。",
      affectedExperts: ["smart_engineer"],
      options: [],
      status: "open",
      kind: pendingMode === "skill" ? "local_execution_authorization" : "general",
      actionType: pendingMode === "skill" ? "resume_skill_run" : null,
      authorizationId: pendingMode === "skill" ? id : null,
      isHighlighted: highlighted,
      criticalPath: true,
      createdAt: "2026-07-08T00:00:00.000Z",
      updatedAt: "2026-07-08T00:00:01.000Z",
    };
  }
  return {
    id,
    projectId: "prj_1",
    title: isCurrent ? "确认硬件方案" : "检查结构依赖",
    description: isCurrent
      ? "需要确认 ESP32 主控和传感器组合。"
      : "结构工程师等待已确认尺寸。",
    priority: isCurrent ? "confirmation" : "blocking",
    reason: isCurrent ? "需要用户确认后再生成 BOM。" : "上游硬件尺寸尚未锁定。",
    affectedExperts: isCurrent ? ["smart_engineer"] : ["structure_engineer"],
    options: isCurrent ? ["确认方案", "继续修改"] : ["等待", "查看依赖"],
    status: "open",
    kind: "general",
    actionType: null,
    authorizationId: null,
    isHighlighted: highlighted,
    criticalPath: !isCurrent,
    createdAt: isCurrent
      ? "2026-07-08T00:00:00.000Z"
      : "2026-07-08T00:00:01.000Z",
    updatedAt: "2026-07-08T00:00:01.000Z",
  };
}

function workspace(
  draft: string,
  activeExpertType: "problem_guide" | "smart_engineer" | "structure_engineer" = "smart_engineer",
  currentPendingResolved = false,
  withPendingItems = true,
  pendingMode: "project" | "skill" | "spoofed" = "project",
  deliveryTrack: "project" | "lesson" = "project",
) {
  const activeExpertId = expertId(activeExpertType);
  const activeConversationId = conversationId(activeExpertType);
  const conversationMessages = pendingMode === "skill"
    ? [skillSourceMessage(activeExpertId, activeConversationId, activeExpertType)]
    : [];
  const experts = [
    {
      id: activeExpertId,
      projectId: "prj_1",
      expertDefinitionId: `expert_def_${activeExpertType}`,
      expertType: activeExpertType,
      conversationId: activeConversationId,
      privateMemoryId: `memory_prj_1_${activeExpertType}`,
      status: "waiting_user",
      workspaceStatus: "awaiting_user",
      currentTask: "继续确认方案",
      addedAt: "2026-07-08T00:00:00.000Z",
      removedAt: null,
    },
  ];
  return {
    project: {
      id: "prj_1",
      name: "测试项目",
      stage: "PROPOSAL_DRAFT",
      profile: { initialIdea: "测试创意" },
      conversationId: activeConversationId,
      activeExpertIds: [activeExpertId],
      activeExpertId,
      sharedContextId: "shared_prj_1",
      coordinatorStateId: "coord_prj_1",
      selectedModel: "deepseek-v4-flash",
      archivedAt: null,
      createdAt: "2026-07-08T00:00:00.000Z",
      updatedAt: "2026-07-08T00:00:00.000Z",
      lastOpenedAt: "2026-07-08T00:00:00.000Z",
      schemaVersion: 22,
    },
    conversation: {
      id: activeConversationId,
      projectId: "prj_1",
      messages: conversationMessages,
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
    draft: {
      projectId: "prj_1",
      projectExpertId: activeExpertId,
      content: draft,
      updatedAt: draft ? "2026-07-08T00:00:00.000Z" : null,
    },
    experts,
    expertDefinitions: expertDefinitions(),
    expertConversations: [
      {
        id: activeConversationId,
        projectId: "prj_1",
        projectExpertId: activeExpertId,
        expertType: activeExpertType,
        expertName: expertLabel(activeExpertType),
        messages: conversationMessages,
        draft: {
          projectId: "prj_1",
          projectExpertId: activeExpertId,
          content: draft,
          updatedAt: draft ? "2026-07-08T00:00:00.000Z" : null,
        },
        activeQuestionId: null,
        activeTurnId: null,
        updatedAt: "2026-07-08T00:00:00.000Z",
      },
    ],
    sharedContext: {
      id: "shared_prj_1",
      projectId: "prj_1",
      revision: 1,
      goals: [
        {
          id: "goal_1",
          field: "项目目标",
          value: "测试创客项目",
          sourceExpertId: activeExpertId,
          status: "confirmed",
          confirmed: true,
          updatedAt: "2026-07-08T00:00:00.000Z",
        },
      ],
      constraints: [],
      requirements: [],
      decisions: [],
      confirmedFacts: [],
      deliveryTrack,
      currentPendingItem: withPendingItems
        ? currentPendingResolved
          ? pendingItem("pending_next", true)
          : pendingItem("pending_current", true, pendingMode)
        : null,
      activeArtifactVersions: [],
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
    coordinator: {
      id: "coord_prj_1",
      projectId: "prj_1",
      currentItem: {
        id: "current_need",
        title: "确认方案 v3",
        description: "右侧工作栏一次只突出一个当前事项。",
        targetExpertId: activeExpertId,
        targetArtifactId: "artifact_solution_prj_1",
        actionLabel: "查看并确认",
        severity: "info",
      },
      currentPendingItem: withPendingItems
        ? currentPendingResolved
          ? pendingItem("pending_next", true)
          : pendingItem("pending_current", true, pendingMode)
        : null,
      pendingItems: withPendingItems
        ? currentPendingResolved
          ? [pendingItem("pending_next", true)]
          : [pendingItem("pending_current", true, pendingMode), pendingItem("pending_next", false)]
        : [],
      expertStatuses: experts,
      conflicts: [],
      dependencies: [],
      updatedAt: "2026-07-08T00:00:00.000Z",
    },
  };
}

function skillSourceMessage(
  projectExpertId: string,
  sourceConversationId: string,
  expertType: "problem_guide" | "smart_engineer" | "structure_engineer",
) {
  return {
    id: "msg_skill_source",
    role: "assistant",
    content: "准备执行已授权的本地检查。",
    metadata: {
      projectExpertId,
      expertType,
      conversationId: sourceConversationId,
      requestTurnId: "turn_skill_request",
      responseTurnId: "turn_skill_response",
    },
    status: "completed",
    model: "deepseek-v4-flash",
    createdAt: "2026-07-08T00:00:00.000Z",
    updatedAt: "2026-07-08T00:00:00.000Z",
  };
}

function pendingResolutionStream(
  expertType: "problem_guide" | "smart_engineer" | "structure_engineer",
  keepOpen = false,
  fail = false,
  signal?: AbortSignal | null,
) {
  const encoder = new TextEncoder();
  const sourceConversationId = conversationId(expertType);
  const base = {
    requestId: "req_pending_resolution",
    messageId: "msg_skill_source",
    model: "deepseek-v4-flash",
    projectId: "prj_1",
    conversationId: sourceConversationId,
    requestTurnId: "turn_pending_resolution",
    responseTurnId: "turn_pending_resolution_response",
    userMessageId: "msg_skill_request",
  };
  const encode = (event: string, data: Record<string, unknown>) =>
    encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);

  return new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(
          encode("chat.started", { ...base, type: "START" }),
        );
        controller.enqueue(
          encode("chat.progress", {
            ...base,
            type: "PROGRESS",
            progress: {
              id: "authorization.confirmed",
              action: "LOCAL_EXECUTION_AUTHORIZATION",
              label: "已确认本地执行授权",
              status: "COMPLETED",
              sequence: 1,
            },
          }),
        );
        controller.enqueue(
          encode("chat.progress", {
            ...base,
            type: "PROGRESS",
            progress: {
              id: "tool.execute",
              action: "LOCAL_TOOL_EXECUTION",
              label: "正在执行本地工具",
              status: "RUNNING",
              sequence: 2,
            },
          }),
        );
        if (keepOpen) {
          const abort = () => controller.error(new Error("aborted"));
          if (signal?.aborted) {
            abort();
          } else {
            signal?.addEventListener("abort", abort, { once: true });
          }
          return;
        }
        if (fail) {
          window.setTimeout(() => {
            controller.enqueue(
              encode("chat.error", {
                ...base,
                type: "ERROR",
                error: {
                  code: "UNKNOWN",
                  message: "受控本地工具执行失败，请重试。",
                  retryable: true,
                  userActions: [{ id: "retry", label: "重试" }],
                },
              }),
            );
            controller.close();
          }, 100);
          return;
        }
        window.setTimeout(() => {
          controller.enqueue(
            encode("chat.progress", {
              ...base,
              type: "PROGRESS",
              progress: {
                id: "tool.execute",
                action: "LOCAL_TOOL_EXECUTION",
                label: "已完成本地工具执行",
                status: "COMPLETED",
                sequence: 2,
              },
            }),
          );
          controller.enqueue(
            encode("chat.completed", { ...base, type: "COMPLETED" }),
          );
          controller.close();
        }, 200);
      },
    }),
    { status: 200, headers: { "Content-Type": "text/event-stream" } },
  );
}

function codeRun(status: "READY_FOR_REVIEW" | "ACCEPTED" | "REJECTED" | "ROLLED_BACK") {
  return {
    id: "code_1",
    projectId: "prj_1",
    specRunId: "spec_1",
    version: 1,
    status,
    workspaceRoot: "workspace://prj_1/code/v1",
    maxRetries: 2,
    retries: 0,
    files: [
      codeFile("README.md", "README", "markdown"),
      codeFile("src/config.py", "CONFIG", "python"),
      codeFile("src/drivers.py", "DRIVER", "python"),
      codeFile("src/main.py", "MAIN", "python"),
      codeFile("tests/test_logic.py", "TEST", "python"),
    ],
    patch: {
      id: "patch_1",
      codeRunId: "code_1",
      projectId: "prj_1",
      baseSnapshotId: null,
      summary: "MicroPython 工程草稿，来自 Spec v1。",
      diff: "diff --git a/src/main.py b/src/main.py\n+while True:\n+    pass\n",
      createdAt: "2026-07-08T00:00:00.000Z",
    },
    testResult: {
      ok: true,
      command: "mock-micropython-unit-tests",
      output: "3 个模拟测试通过；未执行真实 Shell、串口或设备上传。",
      createdAt: "2026-07-08T00:00:00.000Z",
      checks: ["STATIC", "SYNTAX", "SIMULATION"].map((kind) => ({
        kind,
        status: "PASSED",
        command: `validate-${kind.toLowerCase()}`,
        exitCode: 0,
        output: "通过",
      })),
    },
    artifactId: "artifact_code_prj_1",
    artifactVersionId: "artifact_version_code_1",
    staleReason: status === "ROLLED_BACK" ? "代码草稿已回滚，未写入项目工作区。" : null,
    createdAt: "2026-07-08T00:00:00.000Z",
    updatedAt: "2026-07-08T00:00:00.000Z",
    acceptedAt: status === "ACCEPTED" ? "2026-07-08T00:00:00.000Z" : null,
  };
}

function codeFile(path: string, kind: string, language: string) {
  return {
    id: `code_file_${path.replace(/[^a-z0-9]/gi, "_")}`,
    codeRunId: "code_1",
    projectId: "prj_1",
    kind,
    path,
    language,
    content: path === "src/main.py" ? "while True:\n    pass\n" : `${path}\n`,
    createdAt: "2026-07-08T00:00:00.000Z",
  };
}

function editableCodeRun({
  id = "code_1",
  version = 1,
  status = "DRAFT",
  mainContent = "print('MicroPython v1')\n",
  summary = "MicroPython 初始版本",
  baseSnapshotId = null,
}: {
  id?: string;
  version?: number;
  status?: "DRAFT" | "READY_FOR_REVIEW" | "ACCEPTED";
  mainContent?: string;
  summary?: string;
  baseSnapshotId?: string | null;
} = {}) {
  const createdAt = "2026-07-11T00:00:00.000Z";
  const files = [
    {
      id: `file_main_${id}`,
      codeRunId: id,
      projectId: "prj_1",
      kind: "MAIN",
      path: "src/main.py",
      language: "python",
      content: mainContent,
      createdAt,
    },
    {
      id: `file_config_${id}`,
      codeRunId: id,
      projectId: "prj_1",
      kind: "CONFIG",
      path: "src/config.py",
      language: "python",
      content: "BOARD = 'K10'\n",
      createdAt,
    },
  ];
  const checks = ["STATIC", "SYNTAX", "SIMULATION"].map((kind) => ({
    kind,
    status: "NOT_RUN",
    command: `validate-${kind.toLowerCase()}`,
    exitCode: null,
    output: "尚未运行",
  }));
  return {
    id,
    projectId: "prj_1",
    specRunId: "spec_1",
    version,
    status,
    workspaceRoot: `workspace://prj_1/code/v${version}`,
    maxRetries: 2,
    retries: 0,
    files,
    patch: {
      id: `patch_${id}`,
      codeRunId: id,
      projectId: "prj_1",
      baseSnapshotId,
      summary,
      diff: `diff --git a/src/main.py b/src/main.py\n+${mainContent}`,
      createdAt,
    },
    testResult: {
      ok: false,
      command: "not-run-user-edit",
      output: "尚未运行保存后的验证",
      createdAt,
      checks,
    },
    artifactId: "artifact_code_prj_1",
    artifactVersionId: `artifact_version_${id}`,
    hardwareSolutionVersion: 1,
    bomVersion: 1,
    ioMapVersion: 1,
    generatedByExpertId: expertId("smart_engineer"),
    staleReason: null,
    createdAt,
    updatedAt: createdAt,
    acceptedAt: status === "ACCEPTED" ? createdAt : null,
    revisionSource: baseSnapshotId ? "USER" : "MODEL",
    requiresValidation: status !== "ACCEPTED",
  };
}

function codeArtifact(
  run: ReturnType<typeof editableCodeRun>,
  previousVersions: ReadonlyArray<{ id: string }> = [],
) {
  const status = run.status === "ACCEPTED"
    ? "APPROVED"
    : run.status === "READY_FOR_REVIEW"
      ? "NEEDS_REVIEW"
      : "DRAFT";
  const domainStatus = status === "APPROVED"
    ? "confirmed"
    : status === "NEEDS_REVIEW"
      ? "pending_confirmation"
      : "draft";
  const version = {
    id: run.artifactVersionId,
    artifactId: "artifact_code_prj_1",
    projectId: "prj_1",
    version: run.version,
    status,
    domainStatus,
    mimeType: "text/x-python",
    preview: {
      kind: "CODE",
      summary: run.patch.summary,
      code: run.files.find((file) => file.path === "src/main.py")?.content ?? "",
      language: "python",
    },
    dependencies: [],
    producerTaskId: null,
    sourceEntityType: "code",
    sourceEntityId: run.id,
    checksum: `checksum_${run.id}`,
    staleReason: null,
    createdAt: run.createdAt,
    confirmedAt: status === "APPROVED" ? run.acceptedAt : null,
  };
  const hasConfirmedVersion = previousVersions.some(
    (item) => "status" in item && item.status === "APPROVED",
  );
  return {
    id: "artifact_code_prj_1",
    projectId: "prj_1",
    title: "MicroPython 代码",
    kind: "CODE",
    status,
    domainStatus: hasConfirmedVersion ? "confirmed" : domainStatus,
    sourceAgentId: "code-agent",
    ownerExpertId: expertId("smart_engineer"),
    ownerExpertType: "smart_engineer",
    currentVersionId: version.id,
    createdAt: run.createdAt,
    updatedAt: run.updatedAt,
    versions: [
      version,
      ...previousVersions.filter((item) => item.id !== version.id),
    ],
  };
}

function lessonRun(status: "READY_FOR_REVIEW" | "APPROVED" | "REJECTED") {
  return {
    id: "lesson_1",
    projectId: "prj_1",
    specRunId: "spec_1",
    proposalId: "prop_1",
    version: 1,
    status,
    gradeBand: "初中",
    lessonHours: 2,
    files: [
      lessonFile("TEACHER_GUIDE", "教师教案", "lesson/teacher_guide.md"),
      lessonFile("STUDENT_WORKSHEET", "学生任务单", "lesson/student_worksheet.md"),
      lessonFile("RUBRIC", "评价量表", "lesson/rubric.md"),
      lessonFile("SAFETY_NOTES", "安全说明", "lesson/safety_notes.md"),
    ],
    staleReason: status === "REJECTED" ? "需要调整课程教案。" : null,
    createdAt: "2026-07-08T00:00:00.000Z",
    updatedAt: "2026-07-08T00:00:00.000Z",
    confirmedAt: status === "APPROVED" ? "2026-07-08T00:00:00.000Z" : null,
  };
}

function lessonFile(kind: string, title: string, path: string) {
  return {
    id: `lesson_file_${kind.toLowerCase()}`,
    lessonRunId: "lesson_1",
    projectId: "prj_1",
    kind,
    title,
    path,
    mimeType: "text/markdown",
    content: `# ${title}\n\n课堂材料\n`,
    artifactId: `artifact_lesson_${kind.toLowerCase()}`,
    artifactVersionId: `artifact_lesson_${kind.toLowerCase()}_v1`,
    createdAt: "2026-07-08T00:00:00.000Z",
  };
}

function deviceSession(logs = [logEntry("log_1", "INFO", "已建立 Mock MicroPython 会话，未访问真实串口。")]) {
  return {
    id: "device_session_1",
    projectId: "prj_1",
    portId: "mock_port_esp32_s3",
    board: "ESP32-S3",
    status: "READY",
    connectedAt: "2026-07-08T00:00:00.000Z",
    lastSeenAt: "2026-07-08T00:00:00.000Z",
    logs,
  };
}

function firmwareCandidate() {
  return {
    id: "firmware_candidate_1",
    fileName: "k10-micropython.bin",
    sizeBytes: 4096,
    sha256: "a".repeat(64),
    targetChip: "ESP32-S3",
    imageFormat: "esp-image",
    defaultAddress: null,
    compatible: true,
    warnings: ["镜像未声明偏移，必须明确填写写入地址。"],
    expiresAt: "2026-07-08T00:10:00.000Z",
  };
}

function deviceOperation(
  kind: "UPLOAD_CODE" | "FLASH_FIRMWARE",
  status: "DRY_RUN_COMPLETE" | "COMPLETED" = "DRY_RUN_COMPLETE",
  dryRun = true,
) {
  const isFlash = kind === "FLASH_FIRMWARE";
  const completedUploadSteps = !isFlash && !dryRun ? [
    deviceOperationStep("TRANSFER", 0, "写入 MicroPython 文件"),
    deviceOperationStep("VERIFY_FILES", 0, "回读 main.py"),
    deviceOperationStep("RESTART", 0, "重启主控并运行 main.py"),
  ] : [];
  return {
    id: isFlash ? "device_operation_flash_1" : "device_operation_upload_1",
    projectId: "prj_1",
    sessionId: "device_session_1",
    kind,
    status,
    dryRun,
    commandLabel: isFlash ? "esptool" : "mpremote",
    log: isFlash
      ? "固件烧录 Dry Run\n真实命令：未执行\n结果：Dry Run 完成，未擦除 Flash，未烧录固件。"
      : dryRun
        ? "MicroPython 上传 Dry Run\n真实命令：未执行\n结果：Dry Run 完成，未写入真实设备。"
        : "MicroPython 文件上传、回读和重连验证完成。",
    artifactId: "artifact_device_log_prj_1",
    artifactVersionId: isFlash ? "artifact_device_log_prj_1_v2" : "artifact_device_log_prj_1_v1",
    createdAt: "2026-07-08T00:00:00.000Z",
    completedAt: status === "COMPLETED" ? "2026-07-08T00:00:00.000Z" : null,
    phase: "COMPLETE",
    progress: 100,
    cancelable: false,
    steps: completedUploadSteps,
    backup: !isFlash && !dryRun ? {
      backupId: "backup_1",
      fileCount: 1,
      paths: ["main.py"],
      createdAt: "2026-07-08T00:00:00.000Z",
      restorable: true,
    } : null,
    verification: !isFlash && !dryRun ? {
      fileHashes: { "main.py": "a".repeat(64) },
      reconnectExitCode: null,
      runtimeExitCode: null,
      ok: true,
      summary: "文件回读一致，主控已通过正常启动复位运行 main.py。",
      deploymentOk: true,
      restartOk: true,
      managementChannelOk: null,
      warnings: [],
    } : null,
    metadata: !isFlash && !dryRun ? {
      launchMode: "NORMAL_BOOT_RESET",
      postResetProbe: "SKIPPED_TO_PRESERVE_MAIN",
    } : {},
  };
}

function deviceOperationStep(phase: string, exitCode: number, summary: string) {
  return {
    phase,
    status: "COMPLETED",
    exitCode,
    summary,
    startedAt: "2026-07-08T00:00:00.000Z",
    completedAt: "2026-07-08T00:00:00.000Z",
  };
}

function logEntry(id: string, level: "INFO" | "WARNING" | "ERROR", message: string) {
  return {
    id,
    level,
    message,
    createdAt: "2026-07-08T00:00:00.000Z",
  };
}

function proposal() {
  return {
    id: "prop_1",
    projectId: "prj_1",
    solutionId: "sol_1",
    solutionVersion: 1,
    version: 1,
    status: "APPROVED",
    sections: [
      {
        id: "project_overview",
        title: "项目概述",
        content: "完成一个自动浇花项目。",
      },
    ],
    createdAt: "2026-07-08T00:00:00.000Z",
    updatedAt: "2026-07-08T00:00:00.000Z",
    confirmedAt: "2026-07-08T00:00:00.000Z",
    staleReason: null,
  };
}

function specRun(status: "VALIDATED" | "APPROVED" | "REJECTED") {
  return {
    id: "spec_1",
    projectId: "prj_1",
    proposalId: "prop_1",
    version: 1,
    status,
    validation: {
      ok: true,
      checks: [
        {
          dimension: "compatibility",
          severity: "PASS",
          message: "硬件组合通过校验",
          details: "测试 Fixture",
        },
      ],
    },
    files: [
      specFile("PROJECT_SPEC", "spec/project_spec.yaml"),
      specFile("BOM", "spec/bom.yaml"),
      specFile("IO_MAP", "spec/io_map.yaml"),
    ],
    staleReason: status === "REJECTED" ? "需要调整工程规格。" : null,
    createdAt: "2026-07-08T00:00:00.000Z",
    updatedAt: "2026-07-08T00:00:00.000Z",
    confirmedAt: status === "APPROVED" ? "2026-07-08T00:00:00.000Z" : null,
  };
}

function specFile(kind: string, path: string) {
  return {
    id: `file_${kind.toLowerCase()}`,
    specRunId: "spec_1",
    projectId: "prj_1",
    kind,
    path,
    mimeType: "application/x-yaml",
    content: "project:\n  name: 测试项目",
    artifactId: `artifact_spec_${kind.toLowerCase()}`,
    artifactVersionId: `artifact_spec_${kind.toLowerCase()}_v1`,
    createdAt: "2026-07-08T00:00:00.000Z",
  };
}

function artifact(id: string, title: string) {
  const versionId = `${id}_v1`;
  const outdated = id === "artifact_3";
  return {
    id,
    projectId: "prj_1",
    title,
    kind: "DOCUMENT",
    status: "DRAFT",
    domainStatus: outdated ? "outdated" : "draft",
    sourceAgentId: "proposal-agent",
    ownerExpertId: outdated ? expertId("structure_engineer") : expertId("smart_engineer"),
    ownerExpertType: outdated ? "structure_engineer" : "smart_engineer",
    currentVersionId: versionId,
    createdAt: "2026-07-08T00:00:00.000Z",
    updatedAt: "2026-07-08T00:00:00.000Z",
    versions: [
      {
        id: versionId,
        artifactId: id,
        projectId: "prj_1",
        version: 1,
        status: "DRAFT",
        domainStatus: outdated ? "outdated" : "draft",
        mimeType: "text/markdown",
        preview: {
          kind: "DOCUMENT",
          summary: `${title} v1`,
          sections: [
            {
              id: "goal",
              title: "项目目标",
              content: "完成一个可验证的创客项目。",
            },
          ],
        },
        dependencies: [
          {
            artifactId: "sol_1",
            versionId: null,
            version: 1,
            kind: "solution",
            label: "推荐实现方案 v1",
            status: "CONFIRMED",
          },
        ],
        producerTaskId: null,
        sourceEntityType: "proposal",
        sourceEntityId: "prop_1",
        checksum: "0123456789abcdef",
        staleReason: outdated ? "硬件方案 V2 已确认，结构预览依赖旧版尺寸。" : null,
        createdAt: "2026-07-08T00:00:00.000Z",
        confirmedAt: null,
      },
    ],
  };
}

function solution() {
  return {
    id: "sol_3",
    projectId: "prj_1",
    version: 3,
    basedOnVersion: 2,
    status: "DRAFT",
    changeSummary: ["提醒方式：蜂鸣器声音提醒 → RGB LED 灯光提醒"],
    sections: [
      {
        id: "goal",
        title: "项目目标",
        content: "制作桌面饮水提醒器。",
      },
      {
        id: "functional_logic",
        title: "功能逻辑",
        content: "到达提醒时间后，RGB LED 闪烁 30 秒。",
      },
      {
        id: "hardware",
        title: "硬件方案",
        content: "ESP32 主控、RGB LED 模块、确认按键。",
      },
    ],
    artifactId: "artifact_solution_prj_1",
    artifactVersionId: "artifact_solution_prj_1_v3",
    createdAt: "2026-07-08T00:00:00.000Z",
    confirmedAt: null,
  };
}

function solutionArtifact() {
  return {
    id: "artifact_solution_prj_1",
    projectId: "prj_1",
    title: "推荐实现方案",
    kind: "DOCUMENT",
    status: "NEEDS_REVIEW",
    domainStatus: "pending_confirmation",
    sourceAgentId: "solution-agent",
    ownerExpertId: expertId("smart_engineer"),
    ownerExpertType: "smart_engineer",
    currentVersionId: "artifact_solution_prj_1_v3",
    createdAt: "2026-07-08T00:00:00.000Z",
    updatedAt: "2026-07-08T00:00:00.000Z",
    versions: [
      {
        id: "artifact_solution_prj_1_v3",
        artifactId: "artifact_solution_prj_1",
        projectId: "prj_1",
        version: 3,
        status: "NEEDS_REVIEW",
        domainStatus: "pending_confirmation",
        mimeType: "application/vnd.zhangwen.solution+json",
        preview: {
          kind: "DOCUMENT",
          summary: "推荐实现方案 v3；提醒方式已改为灯光提醒",
          sections: [
            {
              id: "hardware",
              title: "硬件方案",
              content: "ESP32 主控、RGB LED 模块、确认按键。",
            },
          ],
        },
        dependencies: [],
        producerTaskId: null,
        sourceEntityType: "solution",
        sourceEntityId: "sol_3",
        checksum: "abcdef0123456789",
        staleReason: null,
        createdAt: "2026-07-08T00:00:00.000Z",
        confirmedAt: null,
      },
    ],
  };
}

function readinessReport(status: "READY" | "NEEDS_ACTION") {
  const ready = status === "READY";
  return {
    projectId: "prj_1",
    overallStatus: status,
    readyCount: ready ? 12 : 4,
    totalCount: 12,
    generatedAt: "2026-07-08T00:00:00.000Z",
    items: [
      readinessItem("PROJECT_BASELINE", "项目基线", "READY"),
      readinessItem("SOLUTION", "推荐实现方案", ready ? "READY" : "NEEDS_ACTION"),
      readinessItem("PROPOSAL", "立项书", ready ? "READY" : "NEEDS_ACTION"),
      readinessItem("EXECUTION_PLAN", "工作计划", ready ? "READY" : "NEEDS_ACTION"),
      readinessItem("SPEC", "工程 Spec", ready ? "READY" : "NEEDS_ACTION"),
      readinessItem("CODE", "代码草稿", ready ? "READY" : "NEEDS_ACTION"),
      readinessItem("DEVICE_DRY_RUN", "设备 Dry Run", ready ? "READY" : "NEEDS_ACTION"),
      readinessItem("CAD", "结构件 CAD", ready ? "READY" : "NEEDS_ACTION"),
      readinessItem("LESSON", "课程教案", ready ? "READY" : "NEEDS_ACTION"),
      readinessItem("PACKAGE", "项目包", ready ? "READY" : "NEEDS_ACTION"),
      readinessItem("ARTIFACTS", "产物汇总", ready ? "READY" : "NEEDS_ACTION"),
      readinessItem("SECURITY", "安全边界", "READY"),
    ],
    externalValidationRequired: [
      "真实 ESP32 串口发现、上传和重启日志需要人工在目标 Windows 机器上执行。",
      "真实 DeepSeek API Key 与付费调用需要用户在设置中手工配置并验证。",
      "真实固件烧录、Flash 擦除和设备文件覆盖不得由自动测试执行。",
    ],
    manualAcceptance: [
      "打开项目后确认中央主对话仍常驻。",
    ],
  };
}

function readinessItem(id: string, label: string, status: "READY" | "NEEDS_ACTION" | "BLOCKED") {
  return {
    id,
    label,
    status,
    required: true,
    message: status === "READY" ? `${label} 已完成。` : `${label} 待处理。`,
    evidence: [`${id}=fixture`],
  };
}

function progressDimension(
  id: "HARDWARE" | "SPECIFICATION" | "CODE" | "TESTING" | "DEPLOYMENT",
  label: string,
  status: "READY" | "NEEDS_ACTION",
) {
  return {
    id,
    label,
    status,
    message: status === "READY" ? `${label}已完成。` : `${label}待处理。`,
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
