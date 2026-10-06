export type Identity = { user_id: number; username: string; permissions: string[]; must_change_password: boolean };

export class APIError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId = '', public traceId = '', public historyId = '', public turnId = '') { super(message); }
}

export async function request(path: string, body?: unknown, userId?: number, signal?: AbortSignal, onTrace?: (traceId: string) => void, method?: 'PATCH' | 'DELETE'): Promise<unknown> {
  const headers: Record<string, string> = {};
  if (body !== undefined) { headers['Content-Type'] = 'application/json'; headers['X-ChatBI-Request'] = 'browser'; }
  if (userId !== undefined) headers['X-ChatBI-User-ID'] = String(userId);
  const response = await fetch(path, { method: method ?? (body === undefined ? 'GET' : 'POST'),
    headers, credentials: 'same-origin', body: body === undefined ? undefined : JSON.stringify(body), signal });
  const header = response.headers.get('X-Trace-ID') ?? '';
  const traceId = /^[0-9a-f]{32}$/.test(header) ? header : '';
  onTrace?.(traceId);
  if (response.status === 204) return null;
  let payload: unknown;
  try { payload = await response.json(); } catch { throw new Error('没有收到有效响应'); }
  if (!response.ok) {
    const p = payload as Record<string, unknown>;
    if (!p || typeof p !== 'object') throw new Error('没有收到有效响应');
    const message = p.error_message ?? p.detail;
    if (typeof message !== 'string') throw new Error('没有收到有效响应');
    throw new APIError(response.status, typeof p.error_code === 'string' ? p.error_code : 'AUTH_ERROR', message, typeof p.request_id === 'string' ? p.request_id : '', traceId,
      typeof p.history_id === 'string' ? p.history_id : '', typeof p.turn_id === 'string' ? p.turn_id : '');
  }
  return payload;
}

export type ExportSource =
  | { kind: 'history_turn'; history_id: string; turn_id: string }
  | { kind: 'saved_result'; saved_result_id: string };

export async function downloadResultExport(source: ExportSource,
  format: 'xlsx' | 'png' | 'pdf', userId: number): Promise<void> {
  const response = await fetch('/api/v1/result-exports', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-ChatBI-Request': 'browser', 'X-ChatBI-User-ID': String(userId) },
    body: JSON.stringify({ source, format }),
  });
  if (!response.ok) {
    let payload: unknown;
    try { payload = await response.json(); } catch { throw new Error('导出请求失败，没有收到有效响应'); }
    const p = payload as Record<string, unknown>;
    if (!p || typeof p.error_message !== 'string') throw new Error('导出请求失败，没有收到有效错误说明');
    throw new APIError(response.status, typeof p.error_code === 'string' ? p.error_code : 'EXPORT_FAILED', p.error_message,
      typeof p.request_id === 'string' ? p.request_id : '');
  }
  const blob = await response.blob();
  if (!blob.size || blob.size > 20 * 1024 * 1024) throw new Error('导出文件大小无效');
  const encodedName = /filename\*=UTF-8''([^;]+)/i.exec(response.headers.get('Content-Disposition') ?? '')?.[1];
  const filename = encodedName ? decodeURIComponent(encodedName) : 'ChatBI-导出';
  const href = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = href; link.download = filename; link.hidden = true;
  document.body.append(link); link.click(); link.remove(); window.setTimeout(() => URL.revokeObjectURL(href), 0);
}

export function identity(value: unknown): Identity {
  const p = value as Identity;
  if (!p || !Number.isSafeInteger(p.user_id) || p.user_id <= 0 || typeof p.username !== 'string'
      || !Array.isArray(p.permissions) || !p.permissions.every(x => typeof x === 'string')
      || typeof p.must_change_password !== 'boolean') throw new Error('身份响应无效');
  return p;
}
