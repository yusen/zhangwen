import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import {
  CodeRuntime,
  CodeRunStatus,
  type CodeRun,
  type CodeRuntimeType,
} from "@zhangwen/contracts";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CodeArtifactEditor } from "../components/floating/CodeArtifactEditor";

vi.mock("../components/floating/MonacoCodeEditor", () => ({
  default: ({
    filePath,
    runtime,
    value,
    onChange,
  }: {
    filePath: string;
    runtime?: CodeRuntimeType;
    value: string;
    onChange: (value: string) => void;
  }) => (
    <textarea
      aria-label={`编辑 ${filePath}`}
      data-runtime={runtime}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("代码产物编辑器", () => {
  it("切换文件、保存不可变新版本，并展示变更与真实验证结果", async () => {
    const base = codeRun();
    const revised = codeRun({
      id: "code_2",
      version: 2,
      baseSnapshotId: "code_1",
      summary: "调整 LED 闪烁间隔",
      mainContent: "INTERVAL_MS = 250\nprint(INTERVAL_MS)\n",
      requiresValidation: true,
    });
    const validated = codeRun({
      ...revised,
      status: CodeRunStatus.READY_FOR_REVIEW,
      requiresValidation: false,
      checks: [
        validationCheck("STATIC", "PASSED", 0, "静态检查通过"),
        validationCheck("SYNTAX", "PASSED", 0, "语法检查通过"),
      ],
    });
    const accepted = codeRun({
      ...validated,
      status: CodeRunStatus.ACCEPTED,
      checks: validated.testResult.checks,
      acceptedAt: "2026-07-19T00:00:00Z",
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/api/projects/prj_1/code/code_1") && method === "GET") {
        return json({ codeRun: base });
      }
      if (url.endsWith("/api/projects/prj_1/code/code_1") && method === "PUT") {
        return json({ codeRun: revised });
      }
      if (url.endsWith("/api/projects/prj_1/code/validate") && method === "POST") {
        return json({ codeRun: validated });
      }
      if (url.endsWith("/api/projects/prj_1/code/accept") && method === "POST") {
        return json({ codeRun: accepted });
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    const onCodeRunChanged = vi.fn();

    render(
      <CodeArtifactEditor
        projectId="prj_1"
        codeRunId="code_1"
        onCodeRunChanged={onCodeRunChanged}
      />,
    );

    expect(await screen.findByRole("tab", { name: "代码" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByRole("tab", { name: "变更" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "验证" })).not.toBeInTheDocument();
    expect(
      screen.getByText("未保存修改智能工程师不可见；保存后下一次回复可见"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "src/main.py" }));
    const editor = await screen.findByRole("textbox", { name: "编辑 src/main.py" });
    fireEvent.change(editor, {
      target: { value: "INTERVAL_MS = 250\nprint(INTERVAL_MS)\n" },
    });
    fireEvent.click(screen.getByRole("tab", { name: "src/config.py" }));
    fireEvent.click(screen.getByRole("tab", { name: "src/main.py" }));
    expect(screen.getByRole("textbox", { name: "编辑 src/main.py" })).toHaveValue(
      "INTERVAL_MS = 250\nprint(INTERVAL_MS)\n",
    );

    fireEvent.change(screen.getByRole("textbox", { name: "变更摘要" }), {
      target: { value: "调整 LED 闪烁间隔" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存新版本" }));

    await waitFor(() => expect(onCodeRunChanged).toHaveBeenCalledWith(revised));
    const putCall = fetchMock.mock.calls.find(
      ([target, init]) => String(target).endsWith("/code/code_1") && init?.method === "PUT",
    );
    expect(putCall).toBeDefined();
    expect(JSON.parse(String(putCall?.[1]?.body))).toEqual({
      baseCodeRunId: "code_1",
      files: [
        { path: "src/main.py", content: "INTERVAL_MS = 250\nprint(INTERVAL_MS)\n" },
        { path: "src/config.py", content: "BOARD = 'K10'\n" },
      ],
      summary: "调整 LED 闪烁间隔",
    });
    expect(await screen.findByText("已保存为不可变新版本 v2。"))
      .toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "变更" }));
    expect(screen.getByText("调整 LED 闪烁间隔")).toBeInTheDocument();
    expect(screen.getByText(/diff --git a\/src\/main.py/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "代码" }));
    const validateAndAcceptButton = screen.getByRole("button", {
      name: "验证并接受代码",
    });
    await waitFor(() => expect(validateAndAcceptButton).toBeEnabled());
    fireEvent.click(validateAndAcceptButton);

    const validation = await screen.findByRole("region", { name: "本地验证结果" });
    expect(await within(validation).findByText("静态检查：通过")).toBeInTheDocument();
    expect(await within(validation).findByText("语法检查：通过")).toBeInTheDocument();
    expect(within(validation).queryByText("模拟验证")).not.toBeInTheDocument();
    const validateCall = fetchMock.mock.calls.find(
      ([target, init]) => String(target).endsWith("/code/validate") && init?.method === "POST",
    );
    expect(JSON.parse(String(validateCall?.[1]?.body))).toEqual({ codeRunId: "code_2" });

    const acceptCall = fetchMock.mock.calls.find(
      ([target, init]) => String(target).endsWith("/code/accept") && init?.method === "POST",
    );
    expect(JSON.parse(String(acceptCall?.[1]?.body))).toEqual({ codeRunId: "code_2" });
    expect(screen.getByText(/代码已接受，可在设备页上传/)).toBeInTheDocument();
    expect(onCodeRunChanged).toHaveBeenLastCalledWith(accepted);
  });

  it("待确认代码在编辑器内完成验证和接受", async () => {
    const reviewable = codeRun({
      status: CodeRunStatus.READY_FOR_REVIEW,
      checks: [
        validationCheck("STATIC", "PASSED", 0, "静态检查通过"),
        validationCheck("SYNTAX", "PASSED", 0, "语法检查通过"),
      ],
    });
    const accepted = codeRun({
      ...reviewable,
      status: CodeRunStatus.ACCEPTED,
      checks: reviewable.testResult.checks,
      acceptedAt: "2026-07-19T00:00:00Z",
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/code/accept") && init?.method === "POST") {
        return json({ codeRun: accepted });
      }
      return json({ codeRun: reviewable });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <CodeArtifactEditor
        projectId="prj_1"
        codeRunId="code_1"
        onCodeRunChanged={vi.fn()}
      />,
    );

    const button = await screen.findByRole("button", { name: "验证并接受代码" });
    fireEvent.click(button);
    expect(await screen.findByText(/代码已接受，可在设备页上传/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(
      ([target]) => String(target).endsWith("/code/accept"),
    )).toBe(true);
  });

  it("409 冲突时保留代码与摘要，不覆盖用户未保存内容", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      if (method === "GET") return json({ codeRun: codeRun() });
      return json(
        { detail: { code: "CODE_REVISION_CONFLICT", message: "当前代码已有更新版本。" } },
        409,
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <CodeArtifactEditor
        projectId="prj_1"
        codeRunId="code_1"
        onCodeRunChanged={vi.fn()}
      />,
    );

    const editor = await screen.findByRole("textbox", { name: "编辑 src/main.py" });
    fireEvent.change(editor, { target: { value: "print('保留我的修改')\n" } });
    fireEvent.change(screen.getByRole("textbox", { name: "变更摘要" }), {
      target: { value: "我的冲突摘要" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存新版本" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "代码已有更新版本，当前未保存内容已保留",
    );
    expect(screen.getByRole("textbox", { name: "编辑 src/main.py" })).toHaveValue(
      "print('保留我的修改')\n",
    );
    expect(screen.getByRole("textbox", { name: "变更摘要" })).toHaveValue(
      "我的冲突摘要",
    );
  });

  it("验证状态只根据真实退出码显示通过", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          codeRun: codeRun({
            status: CodeRunStatus.READY_FOR_REVIEW,
            checks: [validationCheck("STATIC", "PASSED", 1, "退出码异常")],
          }),
        }),
      ),
    );

    render(
      <CodeArtifactEditor
        projectId="prj_1"
        codeRunId="code_1"
        onCodeRunChanged={vi.fn()}
      />,
    );
    const validation = await screen.findByRole("region", { name: "本地验证结果" });
    expect(within(validation).getByText("静态检查：失败（退出码 1）"))
      .toBeInTheDocument();
    expect(within(validation).queryByText("静态检查：通过")).not.toBeInTheDocument();
  });

  it("已接受版本禁用本地验证并显示原因", async () => {
    const fetchMock = vi.fn(async () =>
      json({ codeRun: codeRun({ status: CodeRunStatus.ACCEPTED }) }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <CodeArtifactEditor
        projectId="prj_1"
        codeRunId="code_1"
        onCodeRunChanged={vi.fn()}
      />,
    );

    const validateButton = await screen.findByRole("button", { name: "验证并接受代码" });
    expect(validateButton).toBeDisabled();
    expect(screen.getByText("当前版本已接受，可在设备页上传。"))
      .toBeInTheDocument();
    fireEvent.click(validateButton);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("按 ESP-Claw Lua 运行时展示并保存 Lua 入口文件", async () => {
    const luaFile = codeFile(
      "code_lua_1",
      "scripts/main.lua",
      "MAIN",
      "print('hello claw')\n",
      "lua",
    );
    const luaRun = codeRun({
      id: "code_lua_1",
      runtime: CodeRuntime.ESP_CLAW_LUA,
      entrypoint: "scripts/main.lua",
      files: [luaFile],
    });
    const revised = codeRun({
      ...luaRun,
      id: "code_lua_2",
      version: 2,
      files: [{ ...luaFile, id: "file_lua_2", codeRunId: "code_lua_2", content: "print('updated')\n" }],
      summary: "更新 Lua 入口",
    });
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => (
      init?.method === "PUT" ? json({ codeRun: revised }) : json({ codeRun: luaRun })
    ));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <CodeArtifactEditor
        projectId="prj_1"
        codeRunId="code_lua_1"
        onCodeRunChanged={vi.fn()}
      />,
    );

    const artifact = await screen.findByRole("region", { name: "ESP-Claw Lua 代码产物" });
    const editor = within(artifact).getByRole("textbox", { name: "编辑 scripts/main.lua" });
    expect(editor).toHaveAttribute("data-runtime", CodeRuntime.ESP_CLAW_LUA);
    expect(within(artifact).getByPlaceholderText("概括本次 ESP-Claw Lua 修改"))
      .toBeInTheDocument();

    fireEvent.change(editor, { target: { value: "print('updated')\n" } });
    fireEvent.change(within(artifact).getByRole("textbox", { name: "变更摘要" }), {
      target: { value: "更新 Lua 入口" },
    });
    fireEvent.click(within(artifact).getByRole("button", { name: "保存新版本" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const body = JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body));
    expect(body).toEqual({
      baseCodeRunId: "code_lua_1",
      files: [{ path: "scripts/main.lua", content: "print('updated')\n" }],
      summary: "更新 Lua 入口",
    });
  });

  it.each([
    ["验证失败", CodeRunStatus.FAILED],
    ["待确认", CodeRunStatus.READY_FOR_REVIEW],
  ])("%s 版本仍可重新运行本地验证", async (_label, runStatus) => {
    const current = codeRun({ status: runStatus });
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method && !["GET", "POST"].includes(init.method)) return json({}, 405);
      return json({ codeRun: current });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <CodeArtifactEditor
        projectId="prj_1"
        codeRunId="code_1"
        onCodeRunChanged={vi.fn()}
      />,
    );

    const validateButton = await screen.findByRole("button", { name: "验证并接受代码" });
    expect(validateButton).toBeEnabled();
    fireEvent.click(validateButton);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1]?.[1]?.method).toBe("POST");
  });
});

function codeRun(
  overrides: Partial<CodeRun> & {
    baseSnapshotId?: string | null;
    summary?: string;
    mainContent?: string;
    checks?: CodeRun["testResult"]["checks"];
  } = {},
): CodeRun {
  const id = overrides.id ?? "code_1";
  const mainContent = overrides.mainContent ?? "INTERVAL_MS = 500\nprint(INTERVAL_MS)\n";
  const checks = overrides.checks ?? [
    validationCheck("STATIC", "NOT_RUN", null, "尚未运行"),
    validationCheck("SYNTAX", "NOT_RUN", null, "尚未运行"),
  ];
  return {
    id,
    projectId: "prj_1",
    specRunId: "spec_1",
    version: overrides.version ?? 1,
    status: overrides.status ?? CodeRunStatus.DRAFT,
    runtime: overrides.runtime ?? CodeRuntime.MICROPYTHON,
    entrypoint: overrides.entrypoint ?? "src/main.py",
    workspaceRoot: `workspace://prj_1/code/v${overrides.version ?? 1}`,
    maxRetries: 2,
    retries: 0,
    files: overrides.files ?? [
      codeFile(id, "src/main.py", "MAIN", mainContent),
      codeFile(id, "src/config.py", "CONFIG", "BOARD = 'K10'\n"),
    ],
    patch: {
      id: `patch_${id}`,
      codeRunId: id,
      projectId: "prj_1",
      baseSnapshotId: overrides.baseSnapshotId ?? null,
      summary: overrides.summary ?? "MicroPython 初始版本",
      diff: "diff --git a/src/main.py b/src/main.py\n-INTERVAL_MS = 500\n+INTERVAL_MS = 250\n",
      createdAt: "2026-07-11T00:00:00Z",
    },
    testResult: {
      ok:
        ["STATIC", "SYNTAX"].every((kind) =>
          checks.some((check) => check.kind === kind && check.exitCode === 0),
        ),
      command: checks.every((check) => check.exitCode === null)
        ? "not-run-user-edit"
        : "micropython-local-validation",
      output: checks.map((check) => check.output).join("\n"),
      createdAt: "2026-07-11T00:00:00Z",
      checks,
    },
    artifactId: "artifact_code_prj_1",
    artifactVersionId: `artifact_version_${id}`,
    hardwareSolutionVersion: 1,
    bomVersion: 1,
    ioMapVersion: 1,
    generatedByExpertId: "expert_smart",
    staleReason: null,
    createdAt: "2026-07-11T00:00:00Z",
    updatedAt: "2026-07-11T00:00:00Z",
    acceptedAt: null,
    revisionSource: overrides.revisionSource ?? "USER",
    requiresValidation: overrides.requiresValidation ?? false,
  };
}

function codeFile(
  codeRunId: string,
  path: string,
  kind: "MAIN" | "CONFIG",
  content: string,
  language = "python",
) {
  return {
    id: `file_${path.replace(/\W/g, "_")}`,
    codeRunId,
    projectId: "prj_1",
    kind,
    path,
    language,
    content,
    createdAt: "2026-07-11T00:00:00Z",
  };
}

function validationCheck(
  kind: "STATIC" | "SYNTAX" | "SIMULATION",
  status: "PASSED" | "FAILED" | "NOT_RUN",
  exitCode: number | null,
  output: string,
) {
  return { kind, status, command: `validate-${kind.toLowerCase()}`, exitCode, output };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
