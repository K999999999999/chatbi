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

export function identity(value: unknown): Identity {
  const p = value as Identity;
  if (!p || !Number.isSafeInteger(p.user_id) || p.user_id <= 0 || typeof p.username !== 'string'
      || !Array.isArray(p.permissions) || !p.permissions.every(x => typeof x === 'string')
      || typeof p.must_change_password !== 'boolean') throw new Error('身份响应无效');
  return p;
}
