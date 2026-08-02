import { useEffect, useRef } from "react";
import * as monaco from "monaco-editor";
import { CodeRuntime, type CodeRuntimeType } from "@zhangwen/contracts";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";

interface MonacoWorkerEnvironment {
  getWorker: () => Worker;
}

const workerScope = globalThis as typeof globalThis & {
  MonacoEnvironment?: MonacoWorkerEnvironment;
};

workerScope.MonacoEnvironment ??= {
  getWorker: () => new EditorWorker(),
};

const EDITOR_OPTIONS: monaco.editor.IStandaloneEditorConstructionOptions = {
  automaticLayout: true,
  fixedOverflowWidgets: true,
  fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace",
  fontSize: 13,
  insertSpaces: true,
  lineHeight: 20,
  minimap: { enabled: false },
  overviewRulerLanes: 0,
  padding: { top: 10, bottom: 10 },
  scrollBeyondLastLine: false,
  tabSize: 4,
  wordWrap: "on",
  wrappingIndent: "same",
};

export interface MonacoCodeEditorProps {
  projectId: string;
  codeRunId: string;
  filePath: string;
  runtime?: CodeRuntimeType;
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
}

export default function MonacoCodeEditor({
  projectId,
  codeRunId,
  filePath,
  runtime,
  value,
  onChange,
  readOnly = false,
}: MonacoCodeEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const modelRef = useRef<monaco.editor.ITextModel | null>(null);
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const uri = monaco.Uri.parse(modelPath(projectId, codeRunId, filePath));
    monaco.editor.getModel(uri)?.dispose();
    const model = monaco.editor.createModel(value, languageForPath(filePath, runtime), uri);
    const editor = monaco.editor.create(container, {
      ...EDITOR_OPTIONS,
      ariaLabel: `编辑 ${filePath}`,
      model,
      readOnly,
      theme: "vs",
    });
    const subscription = editor.onDidChangeModelContent(() => {
      onChangeRef.current(model.getValue());
    });
    editorRef.current = editor;
    modelRef.current = model;

    return () => {
      subscription.dispose();
      editor.dispose();
      model.dispose();
      editorRef.current = null;
      modelRef.current = null;
    };
    // `value` is synchronized separately so normal keystrokes do not recreate the editor.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, codeRunId, filePath, runtime]);

  useEffect(() => {
    const model = modelRef.current;
    if (model && model.getValue() !== value) {
      model.setValue(value);
    }
  }, [value]);

  useEffect(() => {
    editorRef.current?.updateOptions({ readOnly });
  }, [readOnly]);

  return <div ref={containerRef} className="code-editor-shell" />;
}

function modelPath(projectId: string, codeRunId: string, filePath: string): string {
  const encodedPath = filePath
    .split("/")
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return [
    "inmemory://zhangwen",
    encodeURIComponent(projectId),
    encodeURIComponent(codeRunId),
    encodedPath,
  ].join("/");
}

export function languageForPath(filePath: string, runtime?: CodeRuntimeType): string {
  const normalized = filePath.toLowerCase();
  if (normalized.endsWith(".py") || normalized.endsWith(".pyi")) return "python";
  if (normalized.endsWith(".lua")) return "lua";
  if (normalized.endsWith(".md") || normalized.endsWith(".markdown")) return "markdown";
  if (normalized.endsWith(".json")) return "json";
  if (runtime === CodeRuntime.ESP_CLAW_LUA) return "lua";
  return "plaintext";
}
