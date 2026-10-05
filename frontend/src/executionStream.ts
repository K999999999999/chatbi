import { reduceExecutionEvent, readExecutionEvents, type ExecutionIdentity, type ExecutionState } from './execution';

export class ExecutionStreamError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

function delay(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException('观察已关闭', 'AbortError')); return; }
    const timer = window.setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, milliseconds);
    const abort = () => { window.clearTimeout(timer); reject(new DOMException('观察已关闭', 'AbortError')); };
    signal.addEventListener('abort', abort, { once: true });
  });
}

async function responseError(response: Response): Promise<ExecutionStreamError> {
  let message = '读取执行状态失败';
  try {
    const body = await response.json() as Record<string, unknown>;
    if (typeof body.error_message === 'string') message = body.error_message;
    else if (typeof body.detail === 'string') message = body.detail;
  } catch { /* keep a non-sensitive fallback */ }
  return new ExecutionStreamError(response.status, message);
}

export async function observeExecution(
  identity: ExecutionIdentity,
  userId: number,
  signal: AbortSignal,
  onProgress: (state: ExecutionState) => void,
): Promise<ExecutionState> {
  const backoff = [250, 500, 1000, 2000, 4000, 8000];
  let state: ExecutionState | null = null;
  let failures = 0;
  while (!signal.aborted) {
    let resnapshot = false;
    try {
      const response = await fetch(`/api/v1/executions/${identity.executionId}/events`, {
        method: 'GET',
        headers: { 'X-ChatBI-User-ID': String(userId) },
        credentials: 'same-origin',
        cache: 'no-store',
        signal,
      });
      if (!response.ok) throw await responseError(response);
      if (!response.headers.get('content-type')?.toLowerCase().startsWith('text/event-stream') || !response.body) {
        throw new ExecutionStreamError(502, '执行状态响应无效');
      }
      for await (const event of readExecutionEvents(response.body, identity)) {
        const reduced = reduceExecutionEvent(state, event);
        if (reduced.authLost) throw new ExecutionStreamError(403, '登录状态或执行权限已失效');
        if (reduced.resnapshot) { resnapshot = true; break; }
        state = reduced.state;
        if (state) {
          onProgress(state);
          if (['succeeded', 'failed', 'cancelled', 'timed_out', 'unconfirmed'].includes(state.status)) return state;
        }
      }
      if (resnapshot) { failures = 0; continue; }
      if (signal.aborted) throw new DOMException('观察已关闭', 'AbortError');
    } catch (error) {
      if (signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) throw error;
      if (error instanceof ExecutionStreamError && (error.status === 401 || error.status === 403 || error.status === 404)) throw error;
      if (error instanceof ExecutionStreamError && error.status < 500 && error.status !== 429) throw error;
      if (error instanceof Error && !(error instanceof TypeError) && !(error instanceof ExecutionStreamError)) {
        throw new ExecutionStreamError(422, '执行状态数据无效');
      }
    }
    await delay(backoff[Math.min(failures, backoff.length - 1)], signal);
    failures += 1;
  }
  throw new DOMException('观察已关闭', 'AbortError');
}
