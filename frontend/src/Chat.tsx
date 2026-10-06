import { useEffect, useRef, useState } from 'react';
import { APIError, downloadResultExport, request, type Identity } from './api';
import { object, querySnapshot, ResultView, type QuerySnapshot } from './results';
import { analysisResult, AnalysisDraft, AnalysisReport, type AnalysisResult } from './Analysis';
import { historyHeader, historyTurn, pageItems, savedResult, type HistoryHeader, type HistoryTurn, type SavedResult } from './history';
import { HistoryPanel } from './HistoryPanel';
import { ExecutionStreamError, observeExecution } from './executionStream';
import type { ExecutionIdentity, ExecutionStage, ExecutionState, ReportDraft } from './execution';

type Mode = 'query' | 'analysis';
type Entry = { id: number; question: string; turnId?: string; saved?: boolean; result?: QuerySnapshot;
  analysis?: AnalysisResult; error?: string; requestId?: string; traceId?: string; executionId?: string;
  operationId?: string; executionStatus?: string; stopReason?: string | null; stage?: ExecutionStage | null;
  completedTasks?: number; totalTasks?: number | null; reportDraft?: ReportDraft | null; draftInterrupted?: boolean };
type Edit = { action: 'save' | 'rename-history' | 'rename-result'; title: string; turnId?: string };
type UncertainExecution = { operationId: string; path: string; body: Record<string, unknown>; historyId: string;
  kind: Mode; entryId: number; question: string };
const stageLabels: Record<ExecutionStage, string> = {
  query_understanding: '理解问题', retrieval: '检索业务语义', sql_generation: '生成查询', sql_validation: '校验查询', query_execution: '执行查询',
  analysis_understanding: '理解分析请求', analysis_plan_validation: '校验分析计划', analysis_query_tasks: '执行分析任务',
  analysis_attribution: '计算归因证据', analysis_report_generation: '生成分析报告', result_saving: '保存正式结果',
};
const blockingErrors = new Set(['HISTORY_BUSY', 'HISTORY_STALE', 'HISTORY_CONTEXT_INCOMPATIBLE', 'HISTORY_SAVE_UNCONFIRMED', 'HISTORY_STORAGE_UNAVAILABLE', 'EXECUTION_LIMIT_REACHED']);
const definiteErrors = new Set(['INVALID_REQUEST', 'AUTHORIZATION_DENIED', 'CANNOT_ANSWER', 'SQL_REJECTED', 'LLM_ERROR', 'CONTEXT_ERROR', 'DATABASE_ERROR',
  'QUERY_TIMEOUT', 'CLARIFICATION_REQUIRED', 'UNSUPPORTED_ANALYSIS', 'EXECUTION_LIMIT_REACHED', 'EXECUTION_UNAVAILABLE', 'HISTORY_BUSY', 'HISTORY_STALE', 'HISTORY_CONTEXT_INCOMPATIBLE',
  'HISTORY_SNAPSHOT_TOO_LARGE', 'HISTORY_SNAPSHOT_UNAVAILABLE', 'HISTORY_OPERATION_CONFLICT', 'HISTORY_UNAVAILABLE']);

export function Chat({ user, onExpired }: { user: Identity; onExpired: () => void }) {
  const [mode, setMode] = useState<Mode>('query');
  const [drafts, setDrafts] = useState<Record<Mode, string>>({ query: '', analysis: '' });
  const [records, setRecords] = useState<Record<Mode, Entry[]>>({ query: [], analysis: [] });
  const [selected, setSelected] = useState<Partial<Record<Mode, HistoryHeader>>>({});
  const [saved, setSaved] = useState<SavedResult>(); const [savedQuery, setSavedQuery] = useState<QuerySnapshot>(); const [savedAnalysis, setSavedAnalysis] = useState<AnalysisResult>();
  const [saving, setSaving] = useState(false); const savingRef = useRef(false);
  const [exporting, setExporting] = useState(false);
  const [pending, setPending] = useState(false); const [blocked, setBlocked] = useState(false); const [notice, setNotice] = useState('');
  const [activeExecutionId, setActiveExecutionId] = useState<string | null>(null);
  const [cancelingExecutionId, setCancelingExecutionId] = useState<string | null>(null);
  const [uncertainExecution, setUncertainExecution] = useState<UncertainExecution | null>(null);
  const [turnCursor, setTurnCursor] = useState<number | null>(null); const [refresh, setRefresh] = useState(0); const [edit, setEdit] = useState<Edit>();
  const [privateClearVersion, setPrivateClearVersion] = useState(0);
  const current = useRef(0); const inFlight = useRef(false); const controller = useRef<AbortController | null>(null); const end = useRef<HTMLDivElement>(null);
  const activeExecution = useRef<string | null>(null); const watching = useRef<{ id: string; controller: AbortController } | null>(null);
  const mounted = useRef(true);
  const header = selected[mode]; const entries = records[mode]; const draft = drafts[mode];
  function locate(kind?: 'history' | 'saved', id?: string) { history.replaceState(null, '', location.pathname + (kind && id ? `#${kind}=${id}` : '')); }
  function begin() { const version = ++current.current; inFlight.current = true; setPending(true); setNotice(''); return version; }
  function done(version: number) { if (version === current.current) { inFlight.current = false; setPending(false); controller.current = null; } }
  function clearPrivate(message: string) {
    watching.current?.controller.abort(); watching.current = null; setActiveExecution(null);
    setRecords({ query: [], analysis: [] }); setSelected({}); setSaved(undefined); setSavedQuery(undefined); setSavedAnalysis(undefined);
    setDrafts({ query: '', analysis: '' }); setUncertainExecution(null); setBlocked(false); setTurnCursor(null); setEdit(undefined);
    setPrivateClearVersion(value => value + 1); setNotice(message); locate();
  }
  function fail(err: unknown, version: number) {
    if (version !== current.current) return;
    if (err instanceof APIError && err.status === 401) { onExpired(); return; }
    if (err instanceof APIError && err.status === 403) { clearPrivate('当前账号已无权查看这些记录，私有内容已清除。'); return; }
    setNotice((err as Error).message);
  }
  async function exportResult(format: 'xlsx' | 'png' | 'pdf', turnId?: string) {
    if (exporting) return;
    const source = saved
      ? { kind: 'saved_result' as const, saved_result_id: saved.id }
      : header && turnId
        ? { kind: 'history_turn' as const, history_id: header.id, turn_id: turnId }
        : undefined;
    if (!source) return;
    setExporting(true); setNotice('正在生成导出文件…');
    try { await downloadResultExport(source, format, user.user_id); setNotice('文件已下载。'); }
    catch (err) { fail(err, current.current); }
    finally { setExporting(false); }
  }
  function entry(t: HistoryTurn, kind: Mode, runId: string | null): Entry {
    const decoded: Entry = { id: t.ordinal, question: t.question, turnId: t.id, saved: t.status === 'succeeded',
      executionId: t.execution_id ?? undefined,
      error: t.status === 'unconfirmed' ? '结果未确认；请刷新后明确选择下一步。' : t.public_error?.error_message };
    if (t.snapshot) {
      if (kind === 'query') { decoded.result = querySnapshot(t.snapshot); decoded.requestId = decoded.result.request_id; }
      else { decoded.analysis = analysisResult(t.snapshot, runId!); decoded.requestId = decoded.analysis.request_id; }
    }
    return decoded;
  }
  function updateExecutionEntry(kind: Mode, turnId: string, update: (item: Entry) => Entry) {
    setRecords(all => ({ ...all, [kind]: all[kind].map(item => item.turnId === turnId ? update(item) : item) }));
  }
  function setActiveExecution(id: string | null) {
    activeExecution.current = id; setActiveExecutionId(id);
  }
  async function cancelExecution(item: Entry, kind: Mode) {
    if (!item.executionId || !item.turnId || cancelingExecutionId) return;
    setCancelingExecutionId(item.executionId);
    try {
      const response = object(await request(
        `/api/v1/executions/${item.executionId}/cancel`, {}, user.user_id, AbortSignal.timeout(30000),
      ));
      const execution = object(response.execution);
      updateExecutionEntry(kind, item.turnId, currentEntry => ({
        ...currentEntry,
        executionStatus: typeof execution.status === 'string' ? execution.status : currentEntry.executionStatus,
        stopReason: typeof execution.stop_reason === 'string' ? execution.stop_reason : currentEntry.stopReason,
      }));
    } catch (error) {
      if (error instanceof APIError && (error.status === 401 || error.status === 403)) {
        fail(error, current.current);
      } else {
        setNotice((error as Error).message || '取消请求未确认；执行状态仍会继续观察。');
      }
    } finally {
      setCancelingExecutionId(value => value === item.executionId ? null : value);
    }
  }
  function startObservation(identity: ExecutionIdentity, kind: Mode) {
    if (!mounted.current) return;
    if (watching.current?.id === identity.executionId) return;
    watching.current?.controller.abort();
    const abort = new AbortController();
    watching.current = { id: identity.executionId, controller: abort };
    setActiveExecution(identity.executionId);
    void (async () => {
      let terminalStatus: string | null = null;
      try {
        const terminal = await observeExecution(identity, user.user_id, abort.signal, state => {
          updateExecutionEntry(kind, identity.turnId, item => ({ ...item, executionId: identity.executionId,
            executionStatus: state.status, stopReason: state.stopReason, stage: state.stage,
            completedTasks: state.completedTasks, totalTasks: state.totalTasks,
            reportDraft: state.draft, draftInterrupted: false }));
        }, state => {
          updateExecutionEntry(kind, identity.turnId, item => ({
            ...item,
            draftInterrupted: !!state?.draft,
          }));
        });
        terminalStatus = terminal.status;
        let response: Record<string, unknown> | null = null;
        let readError: unknown;
        for (const wait of [0, 250, 500, 1000]) {
          if (wait) await new Promise(resolve => window.setTimeout(resolve, wait));
          try { response = object(await request(`/api/v1/executions/${identity.executionId}`, undefined, user.user_id, AbortSignal.timeout(30000))); break; }
          catch (error) {
            readError = error;
            if (error instanceof APIError && (error.status === 401 || error.status === 403 || error.status === 404)) throw error;
          }
        }
        if (!response) throw readError ?? new Error('正式执行结果暂时不可用');
        const nextHeader = historyHeader(response.history);
        const finalTurn = historyTurn(response.turn);
        const result = entry(finalTurn, kind, nextHeader.analysis_run_id);
        result.executionId = identity.executionId; result.executionStatus = terminal.status;
        updateExecutionEntry(kind, identity.turnId, previous => ({ ...result, traceId: result.traceId ?? previous.traceId }));
        setSelected(all => all[kind]?.id === nextHeader.id ? { ...all, [kind]: nextHeader } : all);
        setUncertainExecution(current => current?.historyId === nextHeader.id ? null : current);
        if (kind === 'query') setBlocked(terminal.status === 'unconfirmed');
        setRefresh(value => value + 1);
        if (activeExecution.current === identity.executionId) setActiveExecution(null);
      } catch (error) {
        if (abort.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) return;
        if (watching.current?.id === identity.executionId) watching.current = null;
        if ((error instanceof ExecutionStreamError || error instanceof APIError) && error.status === 401) {
          setRecords({ query: [], analysis: [] }); setSaved(undefined); setSavedQuery(undefined); setSavedAnalysis(undefined); setUncertainExecution(null); onExpired(); return;
        }
        if ((error instanceof ExecutionStreamError || error instanceof APIError) && error.status === 403) {
          clearPrivate('当前身份已无权查看这些记录，私有内容已清除。');
        } else if (terminalStatus !== null) {
          updateExecutionEntry(kind, identity.turnId, item => ({ ...item, result: undefined, analysis: undefined,
            reportDraft: undefined, draftInterrupted: false,
            executionStatus: terminalStatus!, error: '执行已结束，但正式结果暂不可用；请刷新历史确认。' }));
          if (kind === 'query') setBlocked(true);
          if (activeExecution.current === identity.executionId) setActiveExecution(null);
        } else {
          updateExecutionEntry(kind, identity.turnId, item => ({
            ...item,
            draftInterrupted: !!item.reportDraft,
          }));
          setNotice('执行仍可能在后台运行；连接中断后可刷新历史重新观察。');
        }
      } finally {
        if (watching.current?.id === identity.executionId) watching.current = null;
      }
    })();
  }
  async function openHistory(id: string, cursor?: number) {
    if (inFlight.current) return;
    const version = begin();
    try {
      const h = (cursor && header?.id === id) ? header : historyHeader(await request(`/api/v1/histories/${id}`, undefined, user.user_id, AbortSignal.timeout(30000)));
      const p = pageItems(await request(`/api/v1/histories/${id}/turns` + (cursor ? '?cursor=' + cursor : ''), undefined, user.user_id, AbortSignal.timeout(30000)));
      const restored = p.items.map(value => entry(historyTurn(value), h.kind, h.analysis_run_id));
      if (h.active_turn_id && !restored.some(item => item.turnId === h.active_turn_id)) {
        const activeTurn = historyTurn(await request(`/api/v1/histories/${id}/turns/${h.active_turn_id}`, undefined, user.user_id, AbortSignal.timeout(30000)));
        restored.push(entry(activeTurn, h.kind, h.analysis_run_id));
      }
      if (!cursor && h.last_success_turn_id) {
        const t = historyTurn(await request(`/api/v1/histories/${id}/turns/${h.last_success_turn_id}`, undefined, user.user_id, AbortSignal.timeout(30000)));
        const last = entry(t, h.kind, h.analysis_run_id); const position = restored.findIndex(item => item.turnId === t.id);
        if (position >= 0) restored[position] = last; else restored.push(last);
      }
      if (version !== current.current) return;
      setSaved(undefined); setSelected(all => ({ ...all, [h.kind]: h })); setMode(h.kind); setEdit(undefined);
      setRecords(all => ({ ...all, [h.kind]: cursor ? [...all[h.kind].filter(old => !restored.some(item => item.turnId === old.turnId)), ...restored].sort((a, b) => a.id - b.id) : restored }));
      setTurnCursor(p.next_cursor as number | null); if (h.kind === 'query') setBlocked(h.active); locate('history', h.id);
      const activeTurn = restored.find(item => item.turnId === h.active_turn_id);
      if (h.active && activeTurn?.executionId && activeTurn.turnId) {
        startObservation({ executionId: activeTurn.executionId, historyId: h.id, turnId: activeTurn.turnId }, h.kind);
      }
    } catch (err) { fail(err, version); if (version === current.current) setBlocked(true); }
    finally { done(version); }
  }
  async function openSaved(id: string) {
    if (inFlight.current) return;
    const version = begin();
    try {
      const result = savedResult(await request(`/api/v1/saved-results/${id}`, undefined, user.user_id, AbortSignal.timeout(30000)));
      const p = object(result.snapshot);
      const query = result.kind === 'query' ? querySnapshot(p) : undefined;
      const analysis = result.kind === 'analysis' ? analysisResult(p, String(p.analysis_run_id)) : undefined;
      if (version !== current.current) return;
      setSaved(result); setSavedQuery(query); setSavedAnalysis(analysis); setEdit(undefined); locate('saved', id);
    } catch (err) { fail(err, version); } finally { done(version); }
  }
  useEffect(() => {
    mounted.current = true;
    function navigate() {
      current.current++; controller.current?.abort(); inFlight.current = false; setPending(false);
      const match = /^#(history|saved)=([0-9a-f-]{36})$/.exec(location.hash);
      if (match) void (match[1] === 'history' ? openHistory(match[2]) : openSaved(match[2]));
      else { setSaved(undefined); setSelected({}); setRecords({ query: [], analysis: [] }); setBlocked(false); setTurnCursor(null); }
    }
    navigate(); window.addEventListener('hashchange', navigate); window.addEventListener('popstate', navigate);
    return () => { mounted.current = false; current.current++; controller.current?.abort(); watching.current?.controller.abort(); inFlight.current = false; window.removeEventListener('hashchange', navigate); window.removeEventListener('popstate', navigate); };
  }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [entries, pending, mode]);
  async function loadTurn(item: Entry) {
    if (!header || !item.turnId || inFlight.current) return;
    const version = begin();
    try {
      const t = historyTurn(await request(`/api/v1/histories/${header.id}/turns/${item.turnId}`, undefined, user.user_id, AbortSignal.timeout(30000)));
      if (version === current.current) setRecords(all => ({ ...all, [mode]: all[mode].map(old => old.turnId === item.turnId ? entry(t, mode, header.analysis_run_id) : old) }));
    } catch (err) { fail(err, version); } finally { done(version); }
  }
  async function send(resume = false) {
    const target = mode; const question = resume ? header?.first_question : draft.trim();
    if (!question || inFlight.current || activeExecution.current || uncertainExecution || (target === 'query' && blocked) || !user.permissions.includes('query.execute')) return;
    const version = begin(); const abort = new AbortController(); controller.current = abort; setEdit(undefined);
    const entryId = target === 'query' ? Math.max(0, ...entries.map(item => item.id)) + 1 : 1;
    const operationId = crypto.randomUUID(); let traceId = '';
    if (!resume) { setDrafts(all => ({ ...all, [target]: '' })); setRecords(all => ({ ...all, [target]: target === 'query' ? [...all.query, { id: entryId, question, operationId }] : [{ id: entryId, question, operationId }] })); }
    let uncertainCandidate: UncertainExecution | null = null;
    try {
      const h = ((target === 'query' || resume) ? header : undefined) ?? historyHeader(await request('/api/v1/histories',
        { kind: target, first_question: question, operation_id: crypto.randomUUID() }, user.user_id, abort.signal));
      if (version === current.current) { setSelected(all => ({ ...all, [target]: h })); locate('history', h.id); }
      const body = target === 'query' ? { mode: 'query', question, operation_id: operationId, expected_context_revision: h.context_revision }
        : { mode: 'analysis', operation_id: operationId, expected_record_revision: h.record_revision };
      const path = `/api/v1/histories/${h.id}/executions`;
      let response: Record<string, unknown>;
      try {
        response = object(await request(path, body, user.user_id, AbortSignal.timeout(30000), value => { traceId = value; }));
      } catch (submissionError) {
        if (submissionError instanceof APIError && submissionError.status < 500) throw submissionError;
        try {
          response = object(await request(`/api/v1/executions/by-operation/${operationId}`, undefined, user.user_id, AbortSignal.timeout(30000)));
        } catch (recoveryError) {
          if (recoveryError instanceof APIError && (recoveryError.status === 401 || recoveryError.status === 403)) throw recoveryError;
          uncertainCandidate = { operationId, path, body, historyId: h.id, kind: target, entryId, question };
          throw new Error('受理结果暂未确认。可刷新该历史恢复观察；本请求不会自动重发。');
        }
      }
      const next = historyHeader(response.history); const turn = historyTurn(response.turn); const execution = object(response.execution);
      if (typeof execution.id !== 'string' || !execution.id) throw new Error('执行受理响应无效');
      const result = entry(turn, target, next.analysis_run_id);
      result.executionId = execution.id; result.executionStatus = String(execution.status); result.traceId = traceId;
      setUncertainExecution(null);
      if (target === 'analysis') setRecords(all => ({ ...all, analysis: [result] }));
      else setRecords(all => ({ ...all, query: all.query.some(item => item.id === entryId)
        ? all.query.map(item => item.id === entryId ? result : item) : [...all.query, result] }));
      if (version === current.current) setSelected(all => ({ ...all, [target]: next }));
      if (target === 'query') setBlocked(false);
      if (turn.execution_id && turn.execution_id !== execution.id) throw new Error('执行轮次关联不一致');
      startObservation({ executionId: execution.id, historyId: next.id, turnId: turn.id }, target);
    } catch (err) {
      if (err instanceof APIError && err.status === 401) { setUncertainExecution(null); onExpired(); return; }
      if (err instanceof APIError && err.status === 403) { clearPrivate('当前账号已无权查看这些记录，私有内容已清除。'); return; }
      if (uncertainCandidate) {
        const message = '受理结果暂未确认。可刷新该历史恢复观察，或明确重试同一请求。';
        setUncertainExecution(uncertainCandidate);
        if (target === 'query') setBlocked(true);
        const uncertain: Entry = { id: entryId, question: question ?? '', error: message, operationId };
        setRecords(all => ({ ...all, [target]: target === 'analysis' ? [uncertain] : all.query.map(item => item.id === entryId ? uncertain : item) }));
        return;
      }
      const definite = err instanceof APIError && definiteErrors.has(err.code);
      const error = definite ? err.message : '结果未确认，请刷新历史；本请求不会自动重试。';
      if (target === 'query' && (!definite || (err instanceof APIError && blockingErrors.has(err.code)))) setBlocked(true);
      const failed: Entry = { id: entryId, question: question ?? '', error, requestId: err instanceof APIError ? err.requestId : undefined };
      if (target === 'analysis' && version === current.current) setSelected(all => ({ ...all, analysis: all.analysis ? { ...all.analysis, can_resume: false } : undefined }));
      setRecords(all => ({ ...all, [target]: target === 'analysis' ? [failed] : all.query.map(item => item.id === entryId ? failed : item) }));
    } finally { done(version); setRefresh(value => value + 1); }
  }
  async function requery(item?: Entry) {
    if (inFlight.current || activeExecution.current || uncertainExecution || (!saved && (!header || (header.kind === 'query' && !item?.turnId)))) return;
    const version = begin(); const abort = new AbortController(); controller.current = abort;
    const operationId = crypto.randomUUID();
    try {
      const path = saved ? `/api/v1/saved-results/${saved.id}/requery-executions` : `/api/v1/histories/${header!.id}/requery-executions`;
      const body = { operation_id: operationId, ...(!saved && item?.turnId ? { source_turn_id: item.turnId } : {}) };
      let response: Record<string, unknown>;
      try { response = object(await request(path, body, user.user_id, AbortSignal.timeout(30000))); }
      catch (submissionError) {
        if (submissionError instanceof APIError && submissionError.status < 500) throw submissionError;
        response = object(await request(`/api/v1/executions/by-operation/${operationId}`, undefined, user.user_id, AbortSignal.timeout(30000)));
      }
      const next = historyHeader(response.history); const turn = historyTurn(response.turn); const execution = object(response.execution);
      if (typeof execution.id !== 'string' || !execution.id) throw new Error('执行受理响应无效');
      const target: Mode = next.kind;
      const result = entry(turn, target, next.analysis_run_id); result.executionId = execution.id; result.executionStatus = String(execution.status);
      setSaved(undefined); setSavedQuery(undefined); setSavedAnalysis(undefined);
      setRecords(all => ({ ...all, [target]: [result] }));
      if (version === current.current) { setSelected(all => ({ ...all, [target]: next })); setMode(target); locate('history', next.id); }
      startObservation({ executionId: execution.id, historyId: next.id, turnId: turn.id }, target);
    } catch (err) { fail(err, version); }
    finally { done(version); setRefresh(value => value + 1); }
  }
  async function retryUncertainExecution() {
    const pendingOperation = uncertainExecution;
    if (!pendingOperation || inFlight.current || activeExecution.current) return;
    const version = begin(); let traceId = '';
    try {
      let response: Record<string, unknown>;
      try {
        response = object(await request(pendingOperation.path, pendingOperation.body, user.user_id, AbortSignal.timeout(30000), value => { traceId = value; }));
      } catch (submissionError) {
        if (submissionError instanceof APIError && submissionError.status < 500) throw submissionError;
        try {
          response = object(await request(`/api/v1/executions/by-operation/${pendingOperation.operationId}`, undefined, user.user_id, AbortSignal.timeout(30000)));
        } catch (recoveryError) {
          if (recoveryError instanceof APIError && (recoveryError.status === 401 || recoveryError.status === 403)) throw recoveryError;
          throw new Error('仍未找到受理记录；本次未自动继续重试。');
        }
      }
      const next = historyHeader(response.history); const turn = historyTurn(response.turn); const execution = object(response.execution);
      if (typeof execution.id !== 'string' || !execution.id) throw new Error('执行受理响应无效');
      const result = entry(turn, pendingOperation.kind, next.analysis_run_id);
      result.executionId = execution.id; result.executionStatus = String(execution.status); result.traceId = traceId;
      setRecords(all => ({ ...all, [pendingOperation.kind]: pendingOperation.kind === 'analysis' ? [result]
        : all.query.some(item => item.id === pendingOperation.entryId)
          ? all.query.map(item => item.id === pendingOperation.entryId ? result : item) : [...all.query, result] }));
      setUncertainExecution(null); if (pendingOperation.kind === 'query') setBlocked(false);
      if (version === current.current) {
        setSelected(all => ({ ...all, [pendingOperation.kind]: next })); setMode(pendingOperation.kind); locate('history', next.id);
      }
      startObservation({ executionId: execution.id, historyId: next.id, turnId: turn.id }, pendingOperation.kind);
    } catch (error) {
      if (error instanceof APIError && error.status === 401) { setRecords({ query: [], analysis: [] }); setUncertainExecution(null); onExpired(); return; }
      if (error instanceof APIError && error.status === 403) { clearPrivate('当前账号已无权查看这些记录，私有内容已清除。'); return; }
      setNotice((error as Error).message || '受理结果仍未确认。');
    } finally { done(version); }
  }
  async function editName() {
    if (!edit || savingRef.current || (inFlight.current && edit.action !== 'save')) return;
    if (edit.action === 'save') {
      const version = current.current; const source = header; const input = edit;
      if (!source) return;
      savingRef.current = true; setSaving(true);
      try {
        await request('/api/v1/saved-results', { history_id: source.id, turn_id: input.turnId, title: input.title.trim() }, user.user_id, AbortSignal.timeout(30000));
        if (version === current.current) { setEdit(undefined); setNotice('已保存。'); setRefresh(value => value + 1); }
      } catch (err) { fail(err, version); }
      finally { savingRef.current = false; setSaving(false); }
      return;
    }
    const version = begin();
    try {
      if (edit.action === 'rename-history') {
        const h = historyHeader(await request(`/api/v1/histories/${header!.id}`, { title: edit.title.trim(), expected_record_revision: header!.record_revision }, user.user_id, undefined, undefined, 'PATCH'));
        if (version === current.current) setSelected(all => ({ ...all, [mode]: h }));
      } else {
        const result = savedResult(await request(`/api/v1/saved-results/${saved!.id}`, { title: edit.title.trim(), expected_record_revision: saved!.record_revision }, user.user_id, undefined, undefined, 'PATCH'));
        if (version === current.current) setSaved({ ...saved!, ...result });
      }
      if (version === current.current) { setEdit(undefined); setNotice('已保存。'); setRefresh(value => value + 1); }
    } catch (err) { fail(err, version); } finally { done(version); }
  }
  async function remove() {
    if (inFlight.current || (!saved && !header) || !window.confirm(saved ? '删除此成果？历史记录会保留。' : '删除此历史？已另存的成果会保留。')) return;
    const version = begin();
    try {
      const target = saved ?? header!;
      await request(`/api/v1/${saved ? 'saved-results' : 'histories'}/${target.id}`, { expected_record_revision: target.record_revision }, user.user_id, undefined, undefined, 'DELETE');
      if (version === current.current) { setSaved(undefined); if (saved) locate(header ? 'history' : undefined, header?.id); else { setSelected(all => ({ ...all, [mode]: undefined })); setRecords(all => ({ ...all, [mode]: [] })); locate(); setBlocked(false); } setRefresh(value => value + 1); }
    } catch (err) { fail(err, version); } finally { done(version); }
  }
  function newDialogue(target: Mode) {
    if (inFlight.current) return;
    current.current++; setSaved(undefined); setSelected(all => ({ ...all, [target]: undefined })); setMode(target);
    setRecords(all => ({ ...all, [target]: [] })); setDrafts(all => ({ ...all, [target]: '' })); setNotice(''); if (target === 'query') setBlocked(false); setTurnCursor(null); setEdit(undefined); locate();
  }
  function switchMode(target: Mode) { if (!inFlight.current) { setSaved(undefined); setMode(target); setTurnCursor(null); setNotice(''); setEdit(undefined); locate(selected[target] ? 'history' : undefined, selected[target]?.id); } }
  return <div className="chat-layout"><aside className="sidebar"><div className="section-label">工作空间</div>
    <button className={mode === 'query' ? 'mode-selected' : 'mode-button'} aria-pressed={mode === 'query'} disabled={pending} onClick={() => switchMode('query')}>问数</button>
    <button className={mode === 'analysis' ? 'mode-selected' : 'mode-button'} aria-pressed={mode === 'analysis'} disabled={pending} onClick={() => switchMode('analysis')}>经营分析</button>
    <p>{mode === 'query' ? '围绕最近成功结果继续追问。' : '每个完整分析问题独立执行；打开历史只读取报告。'}</p>
    <button className="secondary" disabled={pending} onClick={() => newDialogue(mode)}>{mode === 'query' ? '新建问数对话' : '新建经营分析'}</button>
    <HistoryPanel user={user} pending={pending} refresh={refresh} clearPrivateVersion={privateClearVersion} onExpired={onExpired}
      onForbidden={() => clearPrivate('当前账号已无权查看这些记录，私有内容已清除。')} onOpen={id => void openHistory(id)} onSaved={id => void openSaved(id)}/>
    <div className="scope-note">历史与成果仅当前账号可见。刷新读取保存结果，不自动执行。</div>
  </aside><section className="chat"><div className="chat-top"><h1>{saved ? saved.title : mode === 'query' ? '问数' : '经营分析'}</h1>
    <span>{saved ? '已保存的固定成果' : header?.title ?? '从完整经营问题开始'}</span></div>
    {(header || saved) && <div className="history-actions">
      <button disabled={pending} onClick={() => void (saved ? openSaved(saved.id) : openHistory(header!.id))}>刷新记录</button>
      <button disabled={pending} onClick={() => setEdit({ action: saved ? 'rename-result' : 'rename-history', title: (saved ?? header!).title })}>重命名</button>
      <button disabled={pending || (!saved && !!header?.active)} onClick={() => void remove()}>删除{saved ? '成果' : '历史'}</button>
      {saved && <button disabled={pending} onClick={() => void requery()}>重新查询当前数据</button>}
      {!saved && mode === 'analysis' && header && !header.active && !header.last_success_turn_id && <button disabled={pending || !!activeExecutionId} onClick={() => void requery()}>重新分析当前数据</button>}
      {!saved && mode === 'analysis' && header?.can_resume && <button disabled={pending || !!activeExecutionId} onClick={() => void send(true)}>恢复原分析</button>}
    </div>}
    {edit && <form className="name-editor" onSubmit={event => { event.preventDefault(); void editName(); }}>
      <label>{edit.action === 'save' ? '成果名称' : '记录名称'}<input maxLength={120} value={edit.title} onChange={e => setEdit({ ...edit, title: e.target.value })}/></label>
      <button disabled={saving || (pending && edit.action !== 'save') || !edit.title.trim()}>保存名称</button><button type="button" disabled={saving || (pending && edit.action !== 'save')} onClick={() => setEdit(undefined)}>取消</button></form>}
    <div className="timeline" aria-live="polite">{notice && <p role="alert">{notice}</p>}
      {uncertainExecution && <p role="alert">受理结果暂未确认。可刷新该历史恢复观察，或明确重试同一请求。
        <button disabled={pending} onClick={() => void retryUncertainExecution()}>明确重试同一请求</button></p>}
      {saved ? <article className="turn"><p>成果内容固定；重新查询会创建新历史。</p>
        {savedQuery && <button disabled={exporting || !user.permissions.includes('query.execute')} onClick={() => void exportResult('xlsx')}>{exporting ? '正在导出…' : '下载 XLSX'}</button>}
        {savedQuery && <ResultView data={savedQuery} exportSource={{ kind: 'saved_result', saved_result_id: saved.id }}
          canExport={user.permissions.includes('query.execute')} userId={user.user_id}/>}
        {savedAnalysis && <AnalysisReport result={savedAnalysis} exportSource={{ kind: 'saved_result', saved_result_id: saved.id }}
          canExport={user.permissions.includes('query.execute')} userId={user.user_id}/>}</article> : <>
        {!entries.length && <section className="welcome"><div className="welcome-mark">BI</div><h2>从一个经营问题开始</h2>
          <p>{mode === 'query' ? '例如：2025年2月的人民币净销售额是多少？' : '例如：分析2025年2月相比2025年1月的人民币毛利变化。'}</p></section>}
        {entries.map(item => <article className="turn" key={item.id}><div className="question"><span>你</span><p>{item.question}</p></div>
          {item.executionStatus && ['accepted', 'running', 'stopping'].includes(item.executionStatus) && <>
            <p className="loading" role="status">
              {item.executionStatus === 'stopping'
                ? item.stopReason === 'deadline_exceeded' ? '执行超时，正在停止…'
                  : item.stopReason === 'user_cancelled' ? '正在取消执行…' : '执行权限已变化，正在停止…'
                : item.stage ? stageLabels[item.stage] : '请求已受理，正在准备执行'}
              {item.executionStatus !== 'stopping' && item.totalTasks !== null && item.totalTasks !== undefined
                ? `（已完成 ${item.completedTasks ?? 0} / ${item.totalTasks} 项）` : ''}
            </p>
            {item.executionStatus !== 'stopping' && item.executionId && <button
              disabled={cancelingExecutionId === item.executionId}
              onClick={() => void cancelExecution(item, mode)}
            >{cancelingExecutionId === item.executionId ? '正在提交取消…' : '取消执行'}</button>}
          </>}
          {item.result && <div className="answer"><span className="answer-label">ChatBI</span><ResultView data={item.result}
            exportSource={header && item.turnId ? { kind: 'history_turn', history_id: header.id, turn_id: item.turnId } : undefined}
            canExport={user.permissions.includes('query.execute')} userId={user.user_id}/><details><summary>查看经校验 SQL</summary><pre>{item.result.sql}</pre></details></div>}
          {item.reportDraft && !item.analysis && <div className="answer"><span className="answer-label">ChatBI</span>
            <AnalysisDraft draft={item.reportDraft} interrupted={!!item.draftInterrupted}/></div>}
          {item.analysis && <div className="answer"><span className="answer-label">ChatBI</span><AnalysisReport result={item.analysis}
            exportSource={header && item.turnId ? { kind: 'history_turn', history_id: header.id, turn_id: item.turnId } : undefined}
            canExport={user.permissions.includes('query.execute')} userId={user.user_id}/></div>}
          {item.error && <p role="alert">{item.error}</p>}
          {item.saved && !item.result && !item.analysis && <button disabled={pending} onClick={() => void loadTurn(item)}>查看已保存结果</button>}
          {item.saved && <div className="result-actions"><button disabled={saving} onClick={() => setEdit({ action: 'save', title: header?.title ?? item.question.slice(0, 120), turnId: item.turnId })}>另存成果</button>
            {mode === 'query' && <button disabled={exporting || !user.permissions.includes('query.execute')} onClick={() => void exportResult('xlsx', item.turnId)}>{exporting ? '正在导出…' : '下载 XLSX'}</button>}
            <button disabled={pending || !!activeExecutionId} onClick={() => void requery(item)}>重新查询当前数据</button></div>}
          {(item.requestId || item.traceId) && <details className="diagnostics"><summary>查看请求信息</summary>{item.requestId && <p>请求编号：{item.requestId}</p>}{item.traceId && <p>链路编号：{item.traceId}</p>}</details>}
        </article>)}
        {turnCursor !== null && header && <button disabled={pending} onClick={() => void openHistory(header.id, turnCursor)}>更多轮次</button>}
      </>}{pending && <p className="loading" role="status">正在提交执行请求…</p>}<div ref={end}/></div>
    {!saved && <div className="composer-wrap">{mode === 'query' && blocked && <p role="alert">请刷新记录确认当前状态，或新建对话并补全问题。</p>}
      <form className="composer" onSubmit={event => { event.preventDefault(); void send(); }}><label className="sr-only" htmlFor="question">问题</label>
        <textarea id="question" value={draft} maxLength={8192} onChange={e => setDrafts(all => ({ ...all, [mode]: e.target.value }))} placeholder="输入问题（最多8192字符）；等待期间可以编辑草稿" rows={3}/>
        <div className="composer-actions"><span>{activeExecutionId ? '当前账号已有执行，完成后可继续提交' : '结果完成持久保存后才交付'}</span><button disabled={pending || !!activeExecutionId || !!uncertainExecution || (mode === 'query' && blocked) || !draft.trim() || !user.permissions.includes('query.execute')}>发送</button></div></form></div>}
  </section></div>;
}
