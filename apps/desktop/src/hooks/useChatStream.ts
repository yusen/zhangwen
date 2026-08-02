import { useCallback, useRef } from "react";
import { StreamChunkType } from "@zhangwen/contracts";
import type {
  ChatRequest,
  PersistedChatRequest,
  ProjectStreamChunk,
  StreamChunk,
} from "@zhangwen/contracts";
import {
  cancelChat,
  cancelProjectChat,
  streamChat,
  streamPendingItemResolution,
  streamProjectChat,
} from "../services/llmApi";

interface UseChatStreamOptions {
  onChunk: (chunk: StreamChunk) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

export function useChatStream({ onChunk, onDone, onError }: UseChatStreamOptions) {
  const abortRef = useRef<AbortController | null>(null);
  const requestIdRef = useRef<string | null>(null);
  const activeProjectIdRef = useRef<string | null>(null);
  const settledRef = useRef<Promise<void> | null>(null);
  const generationRef = useRef(0);

  const start = useCallback(
    async (request: ChatRequest) => {
      const generation = ++generationRef.current;
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      activeProjectIdRef.current = null;
      requestIdRef.current = null;

      try {
        const settled = streamChat({
          request,
          signal: controller.signal,
          onChunk: (chunk) => {
            if (generation !== generationRef.current) return;
            if (chunk.type === StreamChunkType.START) {
              requestIdRef.current = chunk.requestId;
            }
            onChunk(chunk);
          },
        });
        settledRef.current = settled;
        await settled;
        if (generation !== generationRef.current) return;
        onDone();
      } catch (error) {
        if (generation !== generationRef.current) return;
        if (controller.signal.aborted) {
          onDone();
          return;
        }
        onError(error instanceof Error ? error.message : "请求失败，请稍后重试。");
      } finally {
        if (generation === generationRef.current && abortRef.current === controller) {
          abortRef.current = null;
          requestIdRef.current = null;
          settledRef.current = null;
        }
      }
    },
    [onChunk, onDone, onError]
  );

  const stop = useCallback(async () => {
    const controller = abortRef.current;
    const requestId = requestIdRef.current;
    const settled = settledRef.current;
    generationRef.current += 1;
    controller?.abort();
    try {
      if (requestId) {
        await cancelChat(requestId);
      }
    } catch {
      // The server also settles an abruptly closed stream; local abort must still run.
    } finally {
      requestIdRef.current = null;
      abortRef.current = null;
      settledRef.current = null;
      await settled?.catch(() => undefined);
    }
  }, []);

  const startProject = useCallback(
    async (projectId: string, request: PersistedChatRequest) => {
      const generation = ++generationRef.current;
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      activeProjectIdRef.current = projectId;
      requestIdRef.current = null;

      try {
        const settled = streamProjectChat({
          projectId,
          request,
          signal: controller.signal,
          onChunk: (chunk: ProjectStreamChunk) => {
            if (generation !== generationRef.current) return;
            if (chunk.type === StreamChunkType.START) {
              requestIdRef.current = chunk.requestId;
            }
            onChunk(chunk);
          },
        });
        settledRef.current = settled;
        await settled;
        if (generation !== generationRef.current) return;
        onDone();
      } catch (error) {
        if (generation !== generationRef.current) return;
        if (controller.signal.aborted) {
          onDone();
          return;
        }
        onError(error instanceof Error ? error.message : "请求失败，请稍后重试。");
      } finally {
        if (generation === generationRef.current && abortRef.current === controller) {
          abortRef.current = null;
          requestIdRef.current = null;
          activeProjectIdRef.current = null;
          settledRef.current = null;
        }
      }
    },
    [onChunk, onDone, onError]
  );

  const stopProject = useCallback(async (projectId: string) => {
    const controller = abortRef.current;
    const requestId = requestIdRef.current;
    const settled = settledRef.current;
    const activeProjectId = activeProjectIdRef.current;
    generationRef.current += 1;
    controller?.abort();
    try {
      if (requestId && activeProjectId === projectId) {
        await cancelProjectChat(projectId, requestId);
      }
    } catch {
      // The server also settles an abruptly closed stream; local abort must still run.
    } finally {
      requestIdRef.current = null;
      activeProjectIdRef.current = null;
      abortRef.current = null;
      settledRef.current = null;
      await settled?.catch(() => undefined);
    }
  }, []);

  const startPendingItemResolution = useCallback(
    async (projectId: string, pendingItemId: string) => {
      const generation = ++generationRef.current;
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      activeProjectIdRef.current = projectId;
      requestIdRef.current = null;
      let terminalError: string | null = null;
      let sawTerminal = false;

      try {
        const settled = streamPendingItemResolution({
          projectId,
          pendingItemId,
          signal: controller.signal,
          onChunk: (chunk: ProjectStreamChunk) => {
            if (generation !== generationRef.current) return;
            if (chunk.type === StreamChunkType.START) {
              requestIdRef.current = chunk.requestId;
            }
            if (
              chunk.type === StreamChunkType.COMPLETED ||
              chunk.type === StreamChunkType.ERROR ||
              chunk.type === StreamChunkType.CANCELED
            ) {
              sawTerminal = true;
            }
            if (
              chunk.type === StreamChunkType.ERROR ||
              chunk.type === StreamChunkType.CANCELED
            ) {
              terminalError = chunk.error?.message ?? "本地执行未完成，请重试。";
            }
            onChunk(chunk);
          },
        });
        settledRef.current = settled;
        await settled;
        if (generation !== generationRef.current) return;
        if (!sawTerminal) {
          throw new Error("本地执行进度流已提前结束，请重试。");
        }
        if (terminalError) {
          throw new Error(terminalError);
        }
        onDone();
      } catch (error) {
        if (generation !== generationRef.current) return;
        if (controller.signal.aborted) {
          onDone();
          return;
        }
        const message =
          error instanceof Error ? error.message : "本地执行未完成，请重试。";
        onError(message);
        throw error instanceof Error ? error : new Error(message);
      } finally {
        if (generation === generationRef.current && abortRef.current === controller) {
          abortRef.current = null;
          requestIdRef.current = null;
          activeProjectIdRef.current = null;
          settledRef.current = null;
        }
      }
    },
    [onChunk, onDone, onError]
  );

  return {
    start,
    stop,
    startProject,
    stopProject,
    startPendingItemResolution,
  };
}
