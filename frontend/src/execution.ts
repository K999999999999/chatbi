export type ExecutionStatus = 'accepted' | 'running' | 'stopping' | 'succeeded' | 'failed' | 'cancelled' | 'timed_out' | 'unconfirmed';
export type ExecutionStage = 'query_understanding' | 'retrieval' | 'sql_generation' | 'sql_validation' | 'query_execution'
  | 'analysis_understanding' | 'analysis_plan_validation' | 'analysis_query_tasks' | 'analysis_attribution'
  | 'analysis_report_generation' | 'result_saving';

export type ExecutionIdentity = { executionId: string; historyId: string; turnId: string };
export type ExecutionState = ExecutionIdentity & { sequence: number; draftGeneration: number; status: ExecutionStatus;
  stage: ExecutionStage | null; completedTasks: number; totalTasks: number | null; stopReason: string | null;
  publicError?: { error_code?: string; error_message?: string } };
export type ExecutionEvent = { version: 1; execution_id: string; history_id?: string; turn_id?: string; sequence: number;
  draft_generation?: number; type: 'snapshot' | 'progress' | 'terminal' | 'auth_lost'; payload: Record<string, unknown> };
export type ReducedExecution = { state: ExecutionState | null; resnapshot: boolean; authLost: boolean };

const stages: ExecutionStage[] = ['query_understanding', 'retrieval', 'sql_generation', 'sql_validation', 'query_execution',
  'analysis_understanding', 'analysis_plan_validation', 'analysis_query_tasks', 'analysis_attribution',
  'analysis_report_generation', 'result_saving'];
const statuses: ExecutionStatus[] = ['accepted', 'running', 'stopping', 'succeeded', 'failed', 'cancelled', 'timed_out', 'unconfirmed'];
const terminal = new Set<ExecutionStatus>(['succeeded', 'failed', 'cancelled', 'timed_out', 'unconfirmed']);
const statusRank = (value: ExecutionStatus) => terminal.has(value) ? 3 : value === 'stopping' ? 2 : value === 'running' ? 1 : 0;
const stopReasons = ['user_cancelled', 'deadline_exceeded', 'authorization_revoked', 'authorization_unavailable'];

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('执行事件格式无效');
  return value as Record<string, unknown>;
}
function nonempty(value: unknown): value is string { return typeof value === 'string' && value.length > 0; }
function safeCount(value: unknown): value is number { return Number.isSafeInteger(value) && Number(value) >= 0; }
function validStatus(value: unknown): value is ExecutionStatus { return statuses.includes(value as ExecutionStatus); }
function validStage(value: unknown): value is ExecutionStage | null { return value === null || stages.includes(value as ExecutionStage); }
function onlyKeys(value: Record<string, unknown>, allowed: string[]): boolean { return Object.keys(value).every(key => allowed.includes(key)); }

export function decodeExecutionEvent(value: unknown, expected: ExecutionIdentity, frameType?: string): ExecutionEvent {
  const event = record(value);
  if (event.version !== 1 || event.execution_id !== expected.executionId || !safeCount(event.sequence)
      || !nonempty(event.type) || (frameType && frameType !== event.type)) throw new Error('执行事件身份或版本无效');
  if (event.type === 'auth_lost') {
    if (Object.keys(event).some(key => !['version', 'execution_id', 'sequence', 'type', 'payload'].includes(key))) throw new Error('执行事件字段无效');
    if (Object.keys(record(event.payload)).length) throw new Error('执行事件包含未授权内容');
    return event as ExecutionEvent;
  }
  if (event.history_id !== expected.historyId || event.turn_id !== expected.turnId
      || !safeCount(event.draft_generation)) throw new Error('执行事件关联身份无效');
  if (Object.keys(event).some(key => !['version', 'execution_id', 'history_id', 'turn_id', 'sequence', 'draft_generation', 'type', 'payload'].includes(key))) throw new Error('执行事件字段无效');
  const payload = record(event.payload);
  if (event.type === 'snapshot') {
    if (!onlyKeys(payload, ['status', 'stage', 'completed_tasks', 'total_tasks', 'stop_reason', 'draft_generation'])
        || !validStatus(payload.status) || !validStage(payload.stage) || !safeCount(payload.completed_tasks)
        || !(payload.total_tasks === null || (safeCount(payload.total_tasks) && Number(payload.total_tasks) > 0))
        || !(payload.stop_reason === null || stopReasons.includes(String(payload.stop_reason)))
        || payload.status === 'stopping' && !stopReasons.includes(String(payload.stop_reason))
        || payload.draft_generation !== event.draft_generation
        || (payload.total_tasks !== null && Number(payload.completed_tasks) > Number(payload.total_tasks))) throw new Error('执行快照字段无效');
  } else if (event.type === 'progress') {
    if (!onlyKeys(payload, ['status', 'stop_reason', 'stage', 'completed_tasks', 'total_tasks'])
        || payload.status !== undefined && !['accepted', 'running', 'stopping'].includes(String(payload.status))) throw new Error('执行状态无效');
    if (payload.stop_reason !== undefined && !stopReasons.includes(String(payload.stop_reason))) throw new Error('执行停止原因无效');
    if (payload.status === 'stopping' && !stopReasons.includes(String(payload.stop_reason))) throw new Error('执行停止原因无效');
    if (payload.stage !== undefined && !validStage(payload.stage)) throw new Error('执行阶段无效');
    if (payload.completed_tasks !== undefined && !safeCount(payload.completed_tasks)) throw new Error('分析任务计数无效');
    if (payload.total_tasks !== undefined && !(payload.total_tasks === null || (safeCount(payload.total_tasks) && Number(payload.total_tasks) > 0))) throw new Error('分析任务总数无效');
    if (payload.completed_tasks !== undefined && payload.total_tasks !== undefined && payload.total_tasks !== null
        && Number(payload.completed_tasks) > Number(payload.total_tasks)) throw new Error('分析任务计数越界');
  } else if (event.type === 'terminal') {
    if (!onlyKeys(payload, ['status', 'public_error']) || !validStatus(payload.status) || !terminal.has(payload.status)) throw new Error('执行终态无效');
    if (payload.public_error !== undefined) {
      const error = record(payload.public_error);
      if (Object.keys(error).some(key => !['error_code', 'error_message'].includes(key))
          || Object.values(error).some(item => typeof item !== 'string')) throw new Error('公开错误字段无效');
    }
  } else throw new Error('未知执行事件类型');
  return event as ExecutionEvent;
}

export function reduceExecutionEvent(current: ExecutionState | null, event: ExecutionEvent): ReducedExecution {
  if (event.type === 'auth_lost') return { state: current, resnapshot: false, authLost: true };
  if (!event.history_id || !event.turn_id || !Number.isSafeInteger(event.draft_generation)) return { state: current, resnapshot: true, authLost: false };
  if (current && (event.execution_id !== current.executionId || event.history_id !== current.historyId || event.turn_id !== current.turnId)) {
    return { state: current, resnapshot: true, authLost: false };
  }
  if (event.type === 'snapshot') {
    if (current && Number(event.draft_generation) < current.draftGeneration) return { state: current, resnapshot: false, authLost: false };
    const payload = event.payload;
    if (!validStatus(payload.status) || !validStage(payload.stage) || !safeCount(payload.completed_tasks)
        || !(payload.total_tasks === null || (safeCount(payload.total_tasks) && Number(payload.total_tasks) > 0))
        || (payload.total_tasks !== null && Number(payload.completed_tasks) > Number(payload.total_tasks))) {
      return { state: current, resnapshot: true, authLost: false };
    }
    if (current) {
      if (event.sequence < current.sequence) {
        if (terminal.has(payload.status) && !terminal.has(current.status)) {
          return { state: { ...current, status: payload.status, stopReason: payload.stop_reason as string | null }, resnapshot: false, authLost: false };
        }
        if (terminal.has(current.status) && payload.status !== current.status) return { state: current, resnapshot: true, authLost: false };
        return { state: current, resnapshot: false, authLost: false };
      }
      if (event.sequence === current.sequence) return { state: current, resnapshot: false, authLost: false };
      if (terminal.has(current.status) && payload.status !== current.status) return { state: current, resnapshot: true, authLost: false };
      if (Number(event.draft_generation) === current.draftGeneration) {
        if (statusRank(payload.status) < statusRank(current.status)
            || (current.stage !== null && (payload.stage === null || stages.indexOf(payload.stage) < stages.indexOf(current.stage)))
            || Number(payload.completed_tasks) < current.completedTasks
            || (current.totalTasks !== null && payload.total_tasks !== current.totalTasks)) {
          return { state: current, resnapshot: true, authLost: false };
        }
      }
    }
    return { state: {
      executionId: event.execution_id, historyId: event.history_id, turnId: event.turn_id, sequence: event.sequence,
      draftGeneration: Number(event.draft_generation), status: payload.status, stage: payload.stage,
      completedTasks: Number(payload.completed_tasks), totalTasks: payload.total_tasks as number | null,
      stopReason: (payload.stop_reason as string | null),
    }, resnapshot: false, authLost: false };
  }
  if (!current) return { state: null, resnapshot: true, authLost: false };
  if (event.sequence <= current.sequence) return { state: current, resnapshot: false, authLost: false };
  if (event.sequence !== current.sequence + 1) return { state: current, resnapshot: true, authLost: false };
  if (terminal.has(current.status)) return { state: current, resnapshot: true, authLost: false };
  const payload = event.payload;
  const nextStatus = payload.status as ExecutionStatus | undefined;
  if (Number(event.draft_generation) < current.draftGeneration) return { state: current, resnapshot: true, authLost: false };
  if (nextStatus && statusRank(nextStatus) < statusRank(current.status)) return { state: current, resnapshot: true, authLost: false };
  const nextStage = payload.stage === undefined ? current.stage : payload.stage as ExecutionStage | null;
  const nextCompleted = payload.completed_tasks === undefined ? current.completedTasks : Number(payload.completed_tasks);
  const nextTotal = payload.total_tasks === undefined ? current.totalTasks : payload.total_tasks as number | null;
  const nextStopReason = payload.stop_reason === undefined ? current.stopReason : payload.stop_reason as string;
  if (nextCompleted < current.completedTasks || (nextTotal !== null && nextCompleted > nextTotal)) return { state: current, resnapshot: true, authLost: false };
  if (current.totalTasks !== null && nextTotal !== current.totalTasks) return { state: current, resnapshot: true, authLost: false };
  if (current.stage !== null && (nextStage === null || stages.indexOf(nextStage) < stages.indexOf(current.stage))) return { state: current, resnapshot: true, authLost: false };
  const next: ExecutionState = { ...current, sequence: event.sequence, draftGeneration: Number(event.draft_generation),
    status: nextStatus ?? current.status, stage: nextStage, completedTasks: nextCompleted, totalTasks: nextTotal,
    stopReason: nextStopReason };
  if (event.type === 'terminal' && payload.public_error) next.publicError = payload.public_error as ExecutionState['publicError'];
  return { state: next, resnapshot: false, authLost: false };
}

export class SSEParser {
  private readonly decoder = new TextDecoder('utf-8', { fatal: true });
  private line = '';
  private data: string[] = [];
  private eventType = '';
  private eventBytes = 0;
  private pendingCR = false;
  private readonly maxEventBytes: number;

  constructor(maxEventBytes = 6 * 1024 * 1024) { this.maxEventBytes = maxEventBytes; }

  feed(chunk: Uint8Array): Array<{ type: string; data: unknown }> {
    const text = this.decoder.decode(chunk, { stream: true });
    const frames: Array<{ type: string; data: unknown }> = [];
    for (const char of text) {
      if (this.pendingCR) {
        this.pendingCR = false;
        this.finishLine(frames);
        if (char === '\n') continue;
      }
      if (char === '\r') this.pendingCR = true;
      else if (char === '\n') this.finishLine(frames);
      else {
        this.line += char;
        const point = char.codePointAt(0)!;
        this.eventBytes += point <= 0x7f ? 1 : point <= 0x7ff ? 2 : point <= 0xffff ? 3 : 4;
        if (this.eventBytes > this.maxEventBytes) throw new Error('执行事件超过网页接收上限');
      }
    }
    return frames;
  }

  finish(): void { this.decoder.decode(); }

  private finishLine(frames: Array<{ type: string; data: unknown }>): void {
    if (!this.line) {
      if (this.data.length) {
        try { frames.push({ type: this.eventType || 'message', data: JSON.parse(this.data.join('\n')) as unknown }); }
        catch { throw new Error('执行事件 JSON 无效'); }
      }
      this.data = []; this.eventType = ''; this.eventBytes = 0; return;
    }
    if (!this.line.startsWith(':')) {
      const separator = this.line.indexOf(':');
      const field = separator < 0 ? this.line : this.line.slice(0, separator);
      let value = separator < 0 ? '' : this.line.slice(separator + 1);
      if (value.startsWith(' ')) value = value.slice(1);
      if (field === 'data') this.data.push(value);
      else if (field === 'event') this.eventType = value;
    }
    this.line = '';
  }
}

export async function* readExecutionEvents(stream: ReadableStream<Uint8Array>, expected: ExecutionIdentity): AsyncGenerator<ExecutionEvent> {
  const reader = stream.getReader();
  const parser = new SSEParser();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) { parser.finish(); return; }
      for (const frame of parser.feed(value)) {
        const decoded = record(frame.data);
        yield decodeExecutionEvent(decoded, expected, frame.type);
      }
    }
  } finally {
    try { await reader.cancel(); } catch { /* stream may already have closed */ }
    reader.releaseLock();
  }
}
