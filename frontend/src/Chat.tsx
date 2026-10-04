import { useEffect, useRef, useState } from 'react';
import { APIError, request, type Identity } from './api';
import { object, querySnapshot, ResultView, type QuerySnapshot } from './results';
import { analysisResult, AnalysisReport, type AnalysisResult } from './Analysis';
import { historyHeader, historyTurn, pageItems, savedResult, type HistoryHeader, type HistoryTurn, type SavedResult } from './history';
import { HistoryPanel } from './HistoryPanel';

type Mode = 'query' | 'analysis';
type Entry = { id: number; question: string; turnId?: string; saved?: boolean; result?: QuerySnapshot;
  analysis?: AnalysisResult; error?: string; requestId?: string; traceId?: string };
type Edit = { action: 'save' | 'rename-history' | 'rename-result'; title: string; turnId?: string };
const blockingErrors = new Set(['HISTORY_BUSY', 'HISTORY_STALE', 'HISTORY_CONTEXT_INCOMPATIBLE', 'HISTORY_SAVE_UNCONFIRMED', 'HISTORY_STORAGE_UNAVAILABLE']);
const definiteErrors = new Set(['INVALID_REQUEST', 'AUTHORIZATION_DENIED', 'CANNOT_ANSWER', 'SQL_REJECTED', 'LLM_ERROR', 'CONTEXT_ERROR', 'DATABASE_ERROR',
  'QUERY_TIMEOUT', 'CLARIFICATION_REQUIRED', 'UNSUPPORTED_ANALYSIS', 'HISTORY_BUSY', 'HISTORY_STALE', 'HISTORY_CONTEXT_INCOMPATIBLE',
  'HISTORY_SNAPSHOT_TOO_LARGE', 'HISTORY_SNAPSHOT_UNAVAILABLE', 'HISTORY_OPERATION_CONFLICT', 'HISTORY_UNAVAILABLE']);

export function Chat({ user, onExpired }: { user: Identity; onExpired: () => void }) {
  const [mode, setMode] = useState<Mode>('query');
  const [drafts, setDrafts] = useState<Record<Mode, string>>({ query: '', analysis: '' });
  const [records, setRecords] = useState<Record<Mode, Entry[]>>({ query: [], analysis: [] });
  const [selected, setSelected] = useState<Partial<Record<Mode, HistoryHeader>>>({});
  const [saved, setSaved] = useState<SavedResult>(); const [savedQuery, setSavedQuery] = useState<QuerySnapshot>(); const [savedAnalysis, setSavedAnalysis] = useState<AnalysisResult>();
  const [saving, setSaving] = useState(false); const savingRef = useRef(false);
  const [pending, setPending] = useState(false); const [blocked, setBlocked] = useState(false); const [notice, setNotice] = useState('');
  const [turnCursor, setTurnCursor] = useState<number | null>(null); const [refresh, setRefresh] = useState(0); const [edit, setEdit] = useState<Edit>();
  const current = useRef(0); const inFlight = useRef(false); const controller = useRef<AbortController | null>(null); const end = useRef<HTMLDivElement>(null);
  const header = selected[mode]; const entries = records[mode]; const draft = drafts[mode];
  function locate(kind?: 'history' | 'saved', id?: string) { history.replaceState(null, '', location.pathname + (kind && id ? `#${kind}=${id}` : '')); }
  function begin() { const version = ++current.current; inFlight.current = true; setPending(true); setNotice(''); return version; }
  function done(version: number) { if (version === current.current) { inFlight.current = false; setPending(false); controller.current = null; } }
  function fail(err: unknown, version: number) {
    if (version !== current.current) return;
    if (err instanceof APIError && err.status === 401) { onExpired(); return; }
    setNotice((err as Error).message);
  }
  function entry(t: HistoryTurn, kind: Mode, runId: string | null): Entry {
    const decoded: Entry = { id: t.ordinal, question: t.question, turnId: t.id, saved: t.status === 'succeeded',
      error: t.status === 'accepted' ? '当前请求仍在执行，请稍后手动刷新。' : t.status === 'unconfirmed' ? '结果未确认；请刷新后明确选择下一步。' : t.public_error?.error_message };
    if (t.snapshot) {
      if (kind === 'query') { decoded.result = querySnapshot(t.snapshot); decoded.requestId = decoded.result.request_id; }
      else { decoded.analysis = analysisResult(t.snapshot, runId!); decoded.requestId = decoded.analysis.request_id; }
    }
    return decoded;
  }
  async function openHistory(id: string, cursor?: number) {
    if (inFlight.current) return;
    const version = begin();
    try {
      const h = (cursor && header?.id === id) ? header : historyHeader(await request(`/api/v1/histories/${id}`, undefined, user.user_id, AbortSignal.timeout(30000)));
      const p = pageItems(await request(`/api/v1/histories/${id}/turns` + (cursor ? '?cursor=' + cursor : ''), undefined, user.user_id, AbortSignal.timeout(30000)));
      const restored = p.items.map(value => entry(historyTurn(value), h.kind, h.analysis_run_id));
      if (!cursor && h.last_success_turn_id) {
        const t = historyTurn(await request(`/api/v1/histories/${id}/turns/${h.last_success_turn_id}`, undefined, user.user_id, AbortSignal.timeout(30000)));
        const last = entry(t, h.kind, h.analysis_run_id); const position = restored.findIndex(item => item.turnId === t.id);
        if (position >= 0) restored[position] = last; else restored.push(last);
      }
      if (version !== current.current) return;
      setSaved(undefined); setSelected(all => ({ ...all, [h.kind]: h })); setMode(h.kind); setEdit(undefined);
      setRecords(all => ({ ...all, [h.kind]: cursor ? [...all[h.kind].filter(old => !restored.some(item => item.turnId === old.turnId)), ...restored].sort((a, b) => a.id - b.id) : restored }));
      setTurnCursor(p.next_cursor as number | null); if (h.kind === 'query') setBlocked(h.active); locate('history', h.id);
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
    function navigate() {
      current.current++; controller.current?.abort(); inFlight.current = false; setPending(false);
      const match = /^#(history|saved)=([0-9a-f-]{36})$/.exec(location.hash);
      if (match) void (match[1] === 'history' ? openHistory(match[2]) : openSaved(match[2]));
      else { setSaved(undefined); setSelected({}); setRecords({ query: [], analysis: [] }); setBlocked(false); setTurnCursor(null); }
    }
    navigate(); window.addEventListener('hashchange', navigate); window.addEventListener('popstate', navigate);
    return () => { current.current++; controller.current?.abort(); inFlight.current = false; window.removeEventListener('hashchange', navigate); window.removeEventListener('popstate', navigate); };
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
    if (!question || inFlight.current || (target === 'query' && blocked) || !user.permissions.includes('query.execute')) return;
    const version = begin(); const abort = new AbortController(); controller.current = abort; setEdit(undefined);
    const timer = window.setTimeout(() => abort.abort(), target === 'query' ? 180000 : 1200000);
    const entryId = target === 'query' ? Math.max(0, ...entries.map(item => item.id)) + 1 : 1;
    if (!resume) { setDrafts(all => ({ ...all, [target]: '' })); setRecords(all => ({ ...all, [target]: target === 'query' ? [...all.query, { id: entryId, question }] : [{ id: entryId, question }] })); }
    let traceId = '';
    try {
      const h = ((target === 'query' || resume) ? header : undefined) ?? historyHeader(await request('/api/v1/histories', { kind: target, first_question: question, operation_id: crypto.randomUUID() }, user.user_id, abort.signal));
      if (version !== current.current) return;
      setSelected(all => ({ ...all, [target]: h })); locate('history', h.id);
      const body = target === 'query' ? { question, operation_id: crypto.randomUUID(), expected_context_revision: h.context_revision }
        : { operation_id: crypto.randomUUID(), expected_record_revision: h.record_revision };
      const response = object(await request(`/api/v1/histories/${h.id}/${target === 'query' ? 'turns' : 'resume'}`, body, user.user_id, abort.signal, value => { traceId = value; }));
      const next = historyHeader(response.history); const result = entry(historyTurn(response.turn), target, next.analysis_run_id);
      if (version !== current.current) return;
      result.traceId = traceId; setSelected(all => ({ ...all, [target]: next })); if (target === 'query') setBlocked(false);
      setRecords(all => ({ ...all, [target]: target === 'analysis' ? [result] : all.query.map(item => item.id === entryId ? result : item) }));
    } catch (err) {
      if (version !== current.current) return;
      if (err instanceof APIError && err.status === 401) { onExpired(); return; }
      const definite = err instanceof APIError && definiteErrors.has(err.code);
      const error = definite ? err.message : '结果未确认，请刷新历史；本请求不会自动重试。';
      if (target === 'query' && (!definite || (err instanceof APIError && blockingErrors.has(err.code)))) setBlocked(true);
      const failed: Entry = { id: entryId, question, error, requestId: err instanceof APIError ? err.requestId : undefined, traceId };
      if (target === 'analysis') setSelected(all => ({ ...all, analysis: all.analysis ? { ...all.analysis, can_resume: false } : undefined }));
      setRecords(all => ({ ...all, [target]: target === 'analysis' ? [failed] : all.query.map(item => item.id === entryId ? failed : item) }));
    } finally { window.clearTimeout(timer); done(version); if (version === current.current) setRefresh(value => value + 1); }
  }
  async function requery(item?: Entry) {
    if (inFlight.current || (!saved && (!header || (header.kind === 'query' && !item?.turnId)))) return;
    const version = begin(); const abort = new AbortController(); controller.current = abort;
    const timer = window.setTimeout(() => abort.abort(), 1200000); let nextId = '';
    try {
      const path = saved ? `/api/v1/saved-results/${saved.id}/requery` : `/api/v1/histories/${header!.id}/requery`;
      const response = object(await request(path, { operation_id: crypto.randomUUID(), ...(!saved && item?.turnId ? { source_turn_id: item.turnId } : {}) }, user.user_id, abort.signal));
      nextId = historyHeader(response.history).id;
    } catch (err) { if (err instanceof APIError) nextId = err.historyId; fail(err, version); }
    finally { window.clearTimeout(timer); done(version); }
    if (version === current.current) { setRefresh(value => value + 1); if (nextId) await openHistory(nextId); }
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
    <HistoryPanel user={user} pending={pending} refresh={refresh} onExpired={onExpired} onOpen={id => void openHistory(id)} onSaved={id => void openSaved(id)}/>
    <div className="scope-note">历史与成果仅当前账号可见。刷新读取保存结果，不自动执行。</div>
  </aside><section className="chat"><div className="chat-top"><h1>{saved ? saved.title : mode === 'query' ? '问数' : '经营分析'}</h1>
    <span>{saved ? '已保存的固定成果' : header?.title ?? '从完整经营问题开始'}</span></div>
    {(header || saved) && <div className="history-actions">
      <button disabled={pending} onClick={() => void (saved ? openSaved(saved.id) : openHistory(header!.id))}>刷新记录</button>
      <button disabled={pending} onClick={() => setEdit({ action: saved ? 'rename-result' : 'rename-history', title: (saved ?? header!).title })}>重命名</button>
      <button disabled={pending || (!saved && !!header?.active)} onClick={() => void remove()}>删除{saved ? '成果' : '历史'}</button>
      {saved && <button disabled={pending} onClick={() => void requery()}>重新查询当前数据</button>}
      {!saved && mode === 'analysis' && header && !header.active && !header.last_success_turn_id && <button disabled={pending} onClick={() => void requery()}>重新分析当前数据</button>}
      {!saved && mode === 'analysis' && header?.can_resume && <button disabled={pending} onClick={() => void send(true)}>恢复原分析</button>}
    </div>}
    {edit && <form className="name-editor" onSubmit={event => { event.preventDefault(); void editName(); }}>
      <label>{edit.action === 'save' ? '成果名称' : '记录名称'}<input maxLength={120} value={edit.title} onChange={e => setEdit({ ...edit, title: e.target.value })}/></label>
      <button disabled={saving || (pending && edit.action !== 'save') || !edit.title.trim()}>保存名称</button><button type="button" disabled={saving || (pending && edit.action !== 'save')} onClick={() => setEdit(undefined)}>取消</button></form>}
    <div className="timeline" aria-live="polite">{notice && <p role="alert">{notice}</p>}
      {saved ? <article className="turn"><p>成果内容固定；重新查询会创建新历史。</p>{savedQuery && <ResultView data={savedQuery}/>}{savedAnalysis && <AnalysisReport result={savedAnalysis}/>}</article> : <>
        {!entries.length && <section className="welcome"><div className="welcome-mark">BI</div><h2>从一个经营问题开始</h2>
          <p>{mode === 'query' ? '例如：2025年2月的人民币净销售额是多少？' : '例如：分析2025年2月相比2025年1月的人民币毛利变化。'}</p></section>}
        {entries.map(item => <article className="turn" key={item.id}><div className="question"><span>你</span><p>{item.question}</p></div>
          {item.result && <div className="answer"><span className="answer-label">ChatBI</span><ResultView data={item.result}/><details><summary>查看经校验 SQL</summary><pre>{item.result.sql}</pre></details></div>}
          {item.analysis && <div className="answer"><span className="answer-label">ChatBI</span><AnalysisReport result={item.analysis}/></div>}
          {item.error && <p role="alert">{item.error}</p>}
          {item.saved && !item.result && !item.analysis && <button disabled={pending} onClick={() => void loadTurn(item)}>查看已保存结果</button>}
          {item.saved && <div className="result-actions"><button disabled={saving} onClick={() => setEdit({ action: 'save', title: header?.title ?? item.question.slice(0, 120), turnId: item.turnId })}>另存成果</button>
            <button disabled={pending} onClick={() => void requery(item)}>重新查询当前数据</button></div>}
          {(item.requestId || item.traceId) && <details className="diagnostics"><summary>查看请求信息</summary>{item.requestId && <p>请求编号：{item.requestId}</p>}{item.traceId && <p>链路编号：{item.traceId}</p>}</details>}
        </article>)}
        {turnCursor !== null && header && <button disabled={pending} onClick={() => void openHistory(header.id, turnCursor)}>更多轮次</button>}
      </>}{pending && <p className="loading" role="status">{mode === 'query' ? '正在查询…' : '正在分析…'}</p>}<div ref={end}/></div>
    {!saved && <div className="composer-wrap">{mode === 'query' && blocked && <p role="alert">请刷新记录确认当前状态，或新建对话并补全问题。</p>}
      <form className="composer" onSubmit={event => { event.preventDefault(); void send(); }}><label className="sr-only" htmlFor="question">问题</label>
        <textarea id="question" value={draft} maxLength={8192} onChange={e => setDrafts(all => ({ ...all, [mode]: e.target.value }))} placeholder="输入问题（最多8192字符）；等待期间可以编辑草稿" rows={3}/>
        <div className="composer-actions"><span>结果完成持久保存后才交付</span><button disabled={pending || (mode === 'query' && blocked) || !draft.trim() || !user.permissions.includes('query.execute')}>发送</button></div></form></div>}
  </section></div>;
}
