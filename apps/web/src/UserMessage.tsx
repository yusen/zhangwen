/** Compact generated test requests, including existing saved verbose prompts. */
export function UserMessage({ content }: { content: string }) {
  const generated = /^(?:我选择先做模块与主控的联调测试。|开始模块联调测试。)\r?\n当前主控：/.test(content);
  if (!generated) return <pre>{content}</pre>;
  const lines = content.split(/\r?\n/);
  const clean = (line: string) => line.replace(/（hw_[^）]+）/g, '');
  const modules = clean(lines[2] ?? '');
  return <div className="integration-request">
    <p>开始模块联调测试</p><p>{clean(lines[1] ?? '')}</p>
    {modules.length <= 120 ? <p>{modules}</p> : <details><summary>查看本次测试模块</summary><p>{modules}</p></details>}
    {lines.length > 3 && <details><summary>原始测试请求</summary><pre>{content}</pre></details>}
  </div>;
}
