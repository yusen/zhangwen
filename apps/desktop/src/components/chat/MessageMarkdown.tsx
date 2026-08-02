import { useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

interface MessageMarkdownProps {
  messageId: string;
  content: string;
  onImportPython?: (messageId: string) => Promise<void> | void;
}

export function MessageMarkdown({ messageId, content, onImportPython }: MessageMarkdownProps) {
  return (
    <div className="message-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={markdownComponents(messageId, onImportPython)}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function markdownComponents(
  messageId: string,
  onImportPython?: MessageMarkdownProps["onImportPython"],
): Components {
  return {
    pre({ children }) {
      return <div className="markdown-code-block">{children}</div>;
    },
    code({ className, children, ...props }) {
      const language = className?.match(/language-([\w-]+)/)?.[1]?.toLowerCase();
      const inline = !className;
      const code = String(children).replace(/\n$/, "");
      if (inline) {
        return (
          <code className={className} {...props}>
            {children}
          </code>
        );
      }
      return (
          <MarkdownCodeBlock
            code={code}
            language={language}
            messageId={messageId}
            onImportPython={onImportPython}
        />
      );
    },
  };
}

function MarkdownCodeBlock({
  code,
  language,
  messageId,
  onImportPython,
}: {
  code: string;
  language?: string;
  messageId: string;
  onImportPython?: MessageMarkdownProps["onImportPython"];
}) {
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isPython = language === "python" || language === "py" || language === "micropython";

  const importCode = async () => {
    if (!onImportPython) return;
    setImporting(true);
    setError(null);
    try {
      await onImportPython(messageId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "代码导入失败。");
    } finally {
      setImporting(false);
    }
  };

  return (
    <section className="markdown-code-card" aria-label={isPython ? "Python 代码" : "代码块"}>
      <header className="markdown-code-card-header">
        <span>{language ?? "代码"}</span>
        {isPython && onImportPython && (
          <button type="button" onClick={() => void importCode()} disabled={importing}>
            {importing ? "保存中..." : "保存到产物"}
          </button>
        )}
      </header>
      <pre>
        <code>{code}</code>
      </pre>
      {error && <p className="message-error" role="alert">{error}</p>}
    </section>
  );
}

export function plainTextFromMarkdownNode(node: ReactNode): string {
  return typeof node === "string" ? node : String(node ?? "");
}
