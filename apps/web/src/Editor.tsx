import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import { basicSetup } from 'codemirror';
import { Annotation, Compartment, EditorSelection, EditorState } from '@codemirror/state';
import { EditorView } from '@codemirror/view';
import { python } from '@codemirror/lang-python';
import { indentSelection } from '@codemirror/commands';
import { indentUnit, HighlightStyle, syntaxHighlighting } from '@codemirror/language';
import { tags } from '@lezer/highlight';

export interface EditorHandle { formatIndentation: () => void }
const externalValue = Annotation.define<boolean>();
export const Editor = forwardRef<EditorHandle, { value: string; onChange: (value: string) => void; zoom?: number; readOnly?: boolean }>(function Editor({ value, onChange, zoom = 100, readOnly = false }, ref) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView>();
  const editing = useRef(new Compartment());
  const callback = useRef(onChange);
  callback.current = onChange;
  useImperativeHandle(ref, () => ({ formatIndentation: () => {
    const instance = view.current;
    if (!instance || instance.state.readOnly) return;
    const selection = instance.state.selection;
    instance.dispatch({ selection: EditorSelection.single(0, instance.state.doc.length) });
    indentSelection(instance);
    const length = instance.state.doc.length;
    instance.dispatch({ selection: EditorSelection.create(selection.ranges.map(range => EditorSelection.range(Math.min(range.anchor, length), Math.min(range.head, length))), selection.mainIndex) });
    instance.focus();
  } }));
  useEffect(() => {
    if (!host.current) return;
    const instance = new EditorView({ parent: host.current, state: EditorState.create({ doc: value, extensions: [
      basicSetup, python(), indentUnit.of('    '), EditorView.lineWrapping,
      syntaxHighlighting(HighlightStyle.define([
        { tag: tags.keyword, color: 'var(--code-keyword)' },
        { tag: [tags.string, tags.number], color: 'var(--code-string)' },
        { tag: tags.comment, color: 'var(--code-comment)' },
        { tag: [tags.standard(tags.variableName), tags.function(tags.variableName)], color: 'var(--code-builtin)' },
      ])),
      editing.current.of([EditorState.readOnly.of(readOnly), EditorView.editable.of(!readOnly)]),
      EditorView.contentAttributes.of({ 'aria-label': 'MicroPython 代码编辑器' }),
      EditorView.updateListener.of(update => { if (update.docChanged && !update.transactions.some(transaction => transaction.annotation(externalValue))) callback.current(update.state.doc.toString()); }),
      EditorView.theme({ '&': { height: '100%', background: 'var(--code-bg)', color: 'var(--ink-1)' }, '.cm-scroller': { overflow: 'auto', fontSize: 'var(--editor-font-size, 14px)', fontFamily: 'Consolas, ui-monospace, monospace', lineHeight: '1.8' }, '.cm-content': { padding: '14px 0', caretColor: 'var(--ink-1)' }, '.cm-gutters': { background: 'var(--code-bg)', color: 'var(--ink-3)', borderRight: '1px solid var(--border)', minWidth: '44px' }, '&.cm-focused': { outline: 'none' }, '.cm-activeLine': { background: 'var(--sel)' }, '.cm-activeLineGutter': { background: 'var(--sel)' }, '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': { background: 'var(--sel)' }, '.cm-cursor': { borderLeftColor: 'var(--ink-1)' }, '.cm-tooltip': { background: 'var(--raised)', color: 'var(--ink-1)', borderColor: 'var(--border)' } }),
    ] }) });
    view.current = instance;
    return () => { instance.destroy(); view.current = undefined; };
    // Editor lifetime is independent of draft updates.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    const instance = view.current;
    // CodeMirror displays LF internally; rendering a CRLF file is not a user edit.
    if (instance && instance.state.doc.toString() !== value.replace(/\r\n?/g, '\n')) instance.dispatch({ changes: { from: 0, to: instance.state.doc.length, insert: value }, annotations: externalValue.of(true) });
  }, [value]);
  useEffect(() => {
    view.current?.dispatch({ effects: editing.current.reconfigure([EditorState.readOnly.of(readOnly), EditorView.editable.of(!readOnly)]) });
  }, [readOnly]);
  return <div className="editor" ref={host} style={{ '--editor-font-size': `${14 * zoom / 100}px` } as React.CSSProperties} />;
});
