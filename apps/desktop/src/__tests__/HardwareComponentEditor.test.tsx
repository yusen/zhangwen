import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HardwareComponentEditor } from "../components/floating/HardwareComponentEditor";

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

describe("器件项目 Markdown 编辑器", () => {
  it("展示文件夹架构，选择 Markdown 并以 revision 保存", async () => {
    const base = componentPackage("revision-1");
    const saved = componentPackage("revision-2", {
      path: "docs/integration.md",
      content: "# 接入\n\n使用 I2C 总线。",
      overridden: true,
    });
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "PUT") return json({ package: saved });
      return json({ package: base });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<HardwareComponentEditor componentId="hw_bme280" />);

    const workspace = await screen.findByRole("region", {
      name: "BME280 环境传感器 器件项目编辑器",
    });
    expect(within(workspace).getByLabelText("文件夹 docs")).toBeInTheDocument();
    fireEvent.click(within(workspace).getByRole("button", { name: /接入说明/ }));

    const editor = within(workspace).getByRole("textbox", {
      name: "编辑 docs/integration.md",
    });
    fireEvent.change(editor, {
      target: { value: "# 接入\n\n使用 I2C 总线。" },
    });
    expect(within(workspace).getByText("有未保存修改")).toBeInTheDocument();
    expect(within(workspace).getByRole("button", { name: /安全说明/ })).toBeDisabled();
    fireEvent.click(within(workspace).getByRole("button", { name: "保存文档" }));

    expect(await within(workspace).findByText(/已保存 docs\/integration.md/))
      .toBeInTheDocument();
    const putCall = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(String(putCall?.[1]?.body ?? "{}"))).toEqual({
      path: "docs/integration.md",
      content: "# 接入\n\n使用 I2C 总线。",
      expectedRevision: "revision-1",
    });
  });

  it("revision 冲突时保留当前 Markdown 草稿", async () => {
    let getCount = 0;
    let putCount = 0;
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "PUT") {
        putCount += 1;
        if (putCount === 1) {
          return json(
            {
              detail: {
                code: "HARDWARE_COMPONENT_PACKAGE_CONFLICT",
                message: "器件项目已被其他操作更新。",
                retryable: true,
              },
            },
            409,
          );
        }
        return json({
          package: componentPackage("revision-3", {
            path: "README.md",
            content: "# 保留我的说明",
            overridden: true,
          }),
        });
      }
      getCount += 1;
      return json({
        package: componentPackage(getCount === 1 ? "revision-1" : "revision-2"),
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<HardwareComponentEditor componentId="hw_bme280" />);

    const editor = await screen.findByRole("textbox", { name: "编辑 README.md" });
    fireEvent.change(editor, { target: { value: "# 保留我的说明" } });
    fireEvent.click(screen.getByRole("button", { name: "保存文档" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("当前 Markdown 草稿仍保留");
    expect(screen.getByRole("textbox", { name: "编辑 README.md" })).toHaveValue(
      "# 保留我的说明",
    );

    fireEvent.click(screen.getByRole("button", { name: "保存文档" }));
    expect(await screen.findByText(/已保存 README.md/)).toBeInTheDocument();
    const putBodies = fetchMock.mock.calls
      .filter(([, init]) => init?.method === "PUT")
      .map(([, init]) => JSON.parse(String(init?.body ?? "{}")));
    expect(putBodies).toHaveLength(2);
    expect(putBodies[1]).toMatchObject({ expectedRevision: "revision-2" });
  });

  it("保存进行中锁定 Markdown 编辑，完成后恢复", async () => {
    let resolveSave: ((response: Response) => void) | undefined;
    const pendingSave = new Promise<Response>((resolve) => {
      resolveSave = resolve;
    });
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "PUT") return pendingSave;
      return json({ package: componentPackage("revision-1") });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<HardwareComponentEditor componentId="hw_bme280" />);
    const editor = await screen.findByRole("textbox", { name: "编辑 README.md" });
    fireEvent.change(editor, { target: { value: "# 保存中的说明" } });
    fireEvent.click(screen.getByRole("button", { name: "保存文档" }));

    await waitFor(() => expect(editor).toHaveAttribute("readonly"));
    resolveSave?.(
      json({
        package: componentPackage("revision-2", {
          path: "README.md",
          content: "# 保存中的说明",
          overridden: true,
        }),
      }),
    );
    expect(await screen.findByText(/已保存 README.md/)).toBeInTheDocument();
    expect(editor).not.toHaveAttribute("readonly");
  });
});

function componentPackage(
  revision: string,
  update?: { path: string; content: string; overridden: boolean },
) {
  const files = [
    file("README.md", "概览", "# BME280", false, "entry" as const),
    file("docs/specifications.md", "规格参数", "# 规格", false),
    file("docs/integration.md", "接入说明", "# 接入", false),
    file("docs/safety.md", "安全说明", "# 安全", false),
  ].map((item) =>
    item.path === update?.path
      ? { ...item, content: update.content, overridden: update.overridden }
      : item,
  );
  return {
    componentId: "hw_bme280",
    componentName: "BME280 环境传感器",
    revision,
    files,
  };
}

function file(
  path: string,
  title: string,
  content: string,
  overridden: boolean,
  kind: "entry" | "reference" = "reference",
) {
  return { path, title, kind, content, overridden };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
