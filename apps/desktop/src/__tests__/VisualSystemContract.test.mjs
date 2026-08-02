import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const mainSource = readFileSync(resolve(process.cwd(), "src/main.tsx"), "utf8");
const visualSystemCss = readFileSync(
  resolve(process.cwd(), "src/styles/visual-system.css"),
  "utf8",
);
const visualWorkspaceCss = readFileSync(
  resolve(process.cwd(), "src/styles/visual-workspace.css"),
  "utf8",
);
const visualSettingsCss = readFileSync(
  resolve(process.cwd(), "src/styles/visual-settings.css"),
  "utf8",
);
const visualHardwareProjectCss = readFileSync(
  resolve(process.cwd(), "src/styles/visual-hardware-project.css"),
  "utf8",
);
const visualRightPanelCss = readFileSync(
  resolve(process.cwd(), "src/styles/visual-right-panel.css"),
  "utf8",
);
const v2ShellCss = readFileSync(
  resolve(process.cwd(), "src/styles/v2-shell.css"),
  "utf8",
);
const topBarSource = readFileSync(
  resolve(process.cwd(), "src/components/layout/TopBar.tsx"),
  "utf8",
);
const authGateSource = readFileSync(
  resolve(process.cwd(), "src/components/auth/AuthGate.tsx"),
  "utf8",
);
const indexHtml = readFileSync(resolve(process.cwd(), "index.html"), "utf8");
const tauriConfig = JSON.parse(
  readFileSync(resolve(process.cwd(), "src-tauri/tauri.conf.json"), "utf8"),
);
const tauriHostSource = readFileSync(
  resolve(process.cwd(), "src-tauri/src/lib.rs"),
  "utf8",
);
const tauriBuildSource = readFileSync(
  resolve(process.cwd(), "src-tauri/build.rs"),
  "utf8",
);

function ruleBody(selector, fromEnd = false, source = visualSystemCss) {
  const index = fromEnd
    ? source.lastIndexOf(selector)
    : source.indexOf(selector);
  expect(index).toBeGreaterThanOrEqual(0);
  const open = source.indexOf("{", index);
  const close = source.indexOf("}", open);
  expect(open).toBeGreaterThan(index);
  expect(close).toBeGreaterThan(open);
  return source.slice(open + 1, close);
}

describe("visual system contract", () => {
  it("uses the supplied Zhangwen logo across desktop and in-app brand surfaces", () => {
    expect(existsSync(resolve(process.cwd(), "public/app-logo.png"))).toBe(true);
    expect(existsSync(resolve(process.cwd(), "src-tauri/icons/icon.ico"))).toBe(true);
    expect(tauriConfig.bundle.icon).toContain("icons/icon.ico");
    expect(indexHtml).toContain('href="/app-logo.png"');
    expect(topBarSource).toContain('src="/app-logo.png"');
    expect(authGateSource).toContain('src="/app-logo.png"');
    expect(tauriHostSource).toContain('app.default_window_icon().cloned()');
    expect(tauriHostSource).toContain("window.set_icon(icon)?");
    expect(tauriBuildSource).toContain("cargo:rerun-if-changed=icons/icon.ico");
    expect(ruleBody(".brand-logo {")).toContain("width: 26px");
  });

  it("loads the visual layers after the legacy stylesheet in ownership order", () => {
    const legacy = mainSource.indexOf('import "./App.css"');
    const tokens = mainSource.indexOf('import "./styles/visual-system.css"');
    const workspace = mainSource.indexOf('import "./styles/visual-workspace.css"');
    const settings = mainSource.indexOf('import "./styles/visual-settings.css"');
    const hardwareProject = mainSource.indexOf(
      'import "./styles/visual-hardware-project.css"',
    );
    const rightPanel = mainSource.indexOf(
      'import "./styles/visual-right-panel.css"',
    );

    expect(legacy).toBeGreaterThanOrEqual(0);
    expect(tokens).toBeGreaterThan(legacy);
    expect(workspace).toBeGreaterThan(tokens);
    expect(settings).toBeGreaterThan(workspace);
    expect(hardwareProject).toBeGreaterThan(settings);
    expect(rightPanel).toBeGreaterThan(hardwareProject);
  });

  it("defines the semantic tokens used by the migrated surfaces", () => {
    [
      "--color-surface-muted",
      "--color-text-primary",
      "--color-text-muted",
      "--color-brand",
      "--color-guide",
      "--color-engineer",
      "--color-structure",
      "--color-success",
      "--color-warning",
      "--color-error",
      "--color-info",
      "--radius-md",
      "--radius-lg",
      "--shadow-sm",
      "--control-height",
      "--motion-fast",
    ].forEach((token) => expect(visualSystemCss).toContain(`${token}:`));
  });

  it("keeps inactive V2 rail controls readable over the dark rail", () => {
    const railButton = ruleBody(
      ".zw-shell .zw-rail-btn {",
      false,
      v2ShellCss,
    );
    const railAvatar = ruleBody(
      ".zw-shell .zw-rail-avatar {",
      false,
      v2ShellCss,
    );
    expect(railButton).toContain("color: var(--zw-rail-ink)");
    expect(railAvatar).toContain("color: var(--zw-rail-ink)");
  });

  it("keeps warning and failed device states visually distinct", () => {
    expect(ruleBody('.device-upload-path li[data-state="warning"]')).toContain(
      "var(--color-warning-light)",
    );
    expect(ruleBody('.device-upload-path li[data-state="failed"]')).toContain(
      "var(--color-error-light)",
    );
    expect(ruleBody('.work-plan-status[data-status="success"]')).toContain(
      "var(--color-success-light)",
    );
    expect(ruleBody('.work-plan-status[data-status="error"]')).toContain(
      "var(--color-error-light)",
    );
  });

  it("keeps mobile connection text and the composer input readable", () => {
    const mobileHealth = ruleBody(".health-indicator {", true);
    expect(mobileHealth).toContain("font-size: 12px");
    expect(mobileHealth).not.toContain("font-size: 0");

    const mobileComposer = ruleBody(".chat-composer-row {", true);
    expect(mobileComposer).toContain("display: grid");
    expect(mobileComposer).toContain("grid-template-columns: minmax(0, 1fr) auto");

    const disabledReason = ruleBody(".chat-disabled-reason {", true);
    expect(disabledReason).toContain("grid-row: 2");
    expect(disabledReason).toContain("grid-column: 1 / -1");
  });

  it("gives expert replies semantic avatars, bounded bubbles, and textual motion status", () => {
    const avatar = ruleBody(".message-avatar {", false, visualWorkspaceCss);
    expect(avatar).toContain("width: 32px");
    expect(avatar).toContain("height: 32px");

    expect(
      ruleBody(
        '.chat-message[data-expert-type="problem_guide"] .message-avatar',
        false,
        visualWorkspaceCss,
      ),
    ).toContain("var(--color-guide)");
    expect(
      ruleBody(
        '.chat-message[data-expert-type="smart_engineer"] .message-avatar',
        false,
        visualWorkspaceCss,
      ),
    ).toContain("var(--color-engineer)");
    expect(
      ruleBody(
        '.chat-message[data-expert-type="structure_engineer"] .message-avatar',
        false,
        visualWorkspaceCss,
      ),
    ).toContain("var(--color-structure)");

    expect(
      ruleBody(".chat-message-assistant .message-body", false, visualWorkspaceCss),
    ).toContain("width: min(640px, 100%)");
    expect(
      ruleBody(".chat-message-assistant {", false, visualWorkspaceCss),
    ).toContain("grid-template-columns: 32px minmax(0, 1fr)");
    expect(
      ruleBody(".message-generation-dots i {", false, visualWorkspaceCss),
    ).toContain("message-generation-bounce");
    expect(
      ruleBody(".message-action-progress {", false, visualWorkspaceCss),
    ).toContain("width: min(440px, 100%)");
    expect(
      ruleBody(
        '.message-action-progress[data-status="waiting"] {',
        false,
        visualWorkspaceCss,
      ),
    ).toContain("var(--color-warning-light)");
    expect(
      ruleBody(
        '.message-action-progress[data-status="failed"] {',
        false,
        visualWorkspaceCss,
      ),
    ).toContain("var(--color-error-light)");
    expect(visualSystemCss).toContain("@media (prefers-reduced-motion: reduce)");
  });

  it("uses the compact prototype hierarchy for grouped clarification", () => {
    const clarificationDock = ruleBody(
      ".clarification-dock {",
      false,
      visualWorkspaceCss,
    );
    expect(clarificationDock).toContain("flex: 0 0 auto");
    expect(clarificationDock).toContain("z-index: 4");
    expect(
      ruleBody(
        ".clarification-dock .clarification-group-card {",
        false,
        visualWorkspaceCss,
      ),
    ).toContain("max-height: min(42vh, 360px)");
    expect(
      ruleBody(
        ".clarification-dock .clarification-group-card {",
        true,
        visualWorkspaceCss,
      ),
    ).toContain("max-height: min(38vh, 300px)");
    expect(
      ruleBody(
        ".clarification-group-header .clarification-type-tag",
        false,
        visualWorkspaceCss,
      ),
    ).toContain("var(--color-guide-light)");
    expect(
      ruleBody(".clarification-progress-track {", false, visualWorkspaceCss),
    ).toContain("height: 4px");
    expect(
      ruleBody(
        ".clarification-group-card .conversation-option {",
        false,
        visualWorkspaceCss,
      ),
    ).toContain("min-height: 32px");
    expect(
      ruleBody(
        ".clarification-group-navigation {",
        false,
        visualWorkspaceCss,
      ),
    ).toContain("grid-template-columns");
    expect(
      ruleBody(
        ".clarification-question-position {",
        false,
        visualWorkspaceCss,
      ),
    ).toContain("text-align: center");
    expect(
      ruleBody("  .clarification-group-card {", true, visualWorkspaceCss),
    ).toContain("padding: 12px");
  });

  it("covers project overlays, empty states, and tool workspaces", () => {
    expect(ruleBody(".project-dialog,", false, visualWorkspaceCss)).toContain(
      "var(--radius-lg)",
    );
    expect(ruleBody(".chat-empty-state,", false, visualWorkspaceCss)).toContain(
      "var(--color-brand)",
    );
    expect(ruleBody(".code-editor-shell,", false, visualWorkspaceCss)).toContain(
      "var(--color-surface-subtle)",
    );
    expect(ruleBody(".chat-message-user .message-markdown h1,", false, visualWorkspaceCss))
      .toContain("#ffffff");
  });

  it("covers settings navigation, knowledge surfaces, and narrow-screen actions", () => {
    expect(ruleBody(".settings-dialog {", false, visualSettingsCss)).toContain(
      "var(--radius-lg)",
    );
    expect(ruleBody('.settings-nav button[aria-current="page"]', false, visualSettingsCss))
      .toContain("var(--color-brand-light)");
    expect(ruleBody(".settings-resource-section .hardware-library {", false, visualSettingsCss))
      .toContain("border: 0");

    const mobileHint = ruleBody(".settings-hint {", true, visualSettingsCss);
    expect(mobileHint).toContain("margin-left: 0");
    const mobileActions = ruleBody(".settings-actions,", true, visualSettingsCss);
    expect(mobileActions).toContain("flex-wrap: wrap");
  });

  it("keeps hardware intake warnings textual and moves the file tree above the editor on phones", () => {
    expect(
      ruleBody(
        ".project-hardware-warning {",
        false,
        visualHardwareProjectCss,
      ),
    ).toContain("var(--color-warning-light)");
    expect(
      ruleBody(
        ".hardware-project-editor {",
        true,
        visualHardwareProjectCss,
      ),
    ).toContain("grid-template-columns: minmax(0, 1fr)");
    expect(
      ruleBody(
        ".hardware-project-tree {",
        true,
        visualHardwareProjectCss,
      ),
    ).toContain("border-bottom: 1px solid var(--color-border)");
  });

  it("maps the prototype right-panel hierarchy without hiding textual tab labels", () => {
    expect(
      ruleBody(".right-panel-tabs .tab-btn {", false, visualRightPanelCss),
    ).toContain("display: inline-flex");
    expect(
      ruleBody(".right-panel-tabpane[hidden] {", false, visualRightPanelCss),
    ).toContain("display: none");
    expect(
      ruleBody(".work-pipeline {", false, visualRightPanelCss),
    ).toContain("display: grid");
    expect(
      ruleBody(".device-upload-path {", false, visualRightPanelCss),
    ).toContain("repeat(4, minmax(0, 1fr))");
  });
});
