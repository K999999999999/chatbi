export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('响应结构无效');
  return value as Record<string, unknown>;
}
