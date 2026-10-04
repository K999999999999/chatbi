import { object, text } from './results';

export type HistoryHeader = { id: string; kind: 'query' | 'analysis'; title: string; first_question: string;
  context_revision: number; record_revision: number; active: boolean; can_continue: boolean; can_resume: boolean;
  last_success_turn_id: string | null; analysis_run_id: string | null };
export type HistoryTurn = { id: string; history_id: string; ordinal: number; question: string;
  status: 'accepted' | 'succeeded' | 'failed' | 'unconfirmed'; public_error: { error_message: string } | null; snapshot?: unknown };
export type SavedResult = { id: string; kind: 'query' | 'analysis'; title: string; record_revision: number;
  source_history_id: string; source_turn_id: string; snapshot?: unknown };
export function savedResult(value: unknown): SavedResult {
  const p = object(value);
  text(p.id); text(p.title); text(p.source_history_id); text(p.source_turn_id);
  if (!['query', 'analysis'].includes(String(p.kind)) || !Number.isSafeInteger(p.record_revision) || Number(p.record_revision) < 0) throw new Error('成果响应无效');
  return p as SavedResult;
}
export function historyHeader(value: unknown): HistoryHeader {
  const p = object(value);
  if (!['query', 'analysis'].includes(String(p.kind)) || !Number.isSafeInteger(p.context_revision)
      || Number(p.context_revision) < 0 || !Number.isSafeInteger(p.record_revision) || Number(p.record_revision) < 0
      || typeof p.active !== 'boolean' || typeof p.can_continue !== 'boolean' || typeof p.can_resume !== 'boolean'
      || !(p.last_success_turn_id === null || typeof p.last_success_turn_id === 'string')
      || !(p.analysis_run_id === null || typeof p.analysis_run_id === 'string')) throw new Error('历史响应无效');
  text(p.id); text(p.title); text(p.first_question);
  return p as HistoryHeader;
}
export function historyTurn(value: unknown): HistoryTurn {
  const p = object(value);
  text(p.id); text(p.history_id); text(p.question);
  if (!Number.isSafeInteger(p.ordinal) || Number(p.ordinal) < 1
      || !['accepted', 'succeeded', 'failed', 'unconfirmed'].includes(String(p.status))) throw new Error('历史轮次响应无效');
  if (p.public_error !== null) text(object(p.public_error).error_message);
  return p as HistoryTurn;
}
export function pageItems(value: unknown): { items: unknown[]; next_cursor: string | number | null } {
  const p = object(value);
  if (!Array.isArray(p.items) || !(p.next_cursor === null || typeof p.next_cursor === 'string' || Number.isSafeInteger(p.next_cursor))) throw new Error('分页响应无效');
  return p as { items: unknown[]; next_cursor: string | number | null };
}
