import { CodeRuntime } from "@zhangwen/contracts";
import { describe, expect, it } from "vitest";
import { languageForPath } from "../components/floating/MonacoCodeEditor";

describe("Monaco 代码语言选择", () => {
  it("按 Lua 扩展名或 ESP-Claw Lua 运行时选择 Lua", () => {
    expect(languageForPath("scripts/main.lua", CodeRuntime.MICROPYTHON)).toBe("lua");
    expect(languageForPath("scripts/entry", CodeRuntime.ESP_CLAW_LUA)).toBe("lua");
  });

  it("保留既有 Python 与普通文本识别", () => {
    expect(languageForPath("src/main.py", CodeRuntime.MICROPYTHON)).toBe("python");
    expect(languageForPath("README.txt", CodeRuntime.MICROPYTHON)).toBe("plaintext");
  });
});
