import { useEffect, useRef, useState } from 'react';
import { APIError, request, type Identity } from './api';
import { queryResult, ResultView, type QueryResult } from './results';
import { analysisResult, AnalysisReport, type AnalysisResult } from './Analysis';

type Mode = 'query' | 'analysis';
type Entry = { id: number; question: string; runId?: string; result?: QueryResult;
  analysis?: AnalysisResult; error?: string; uncertain?: boolean; retryable?: boolean; requestId?: string; traceId?: string };
const definiteErrors = new Set(['INVALID_REQUEST', 'AUTHORIZATION_DENIED', 'AUTHENTICATION_UNAVAILABLE',
  'CANNOT_ANSWER', 'SQL_REJECTED', 'LLM_ERROR', 'CONTEXT_ERROR', 'DATABASE_ERROR', 'QUERY_TIMEOUT',
  'CONVERSATION_UNAVAILABLE', 'CLARIFICATION_REQUIRED', 'UNSUPPORTED_ANALYSIS', 'CONVERSATION_CONFLICT']);
const retryableErrors = new Set(['AUTHENTICATION_UNAVAILABLE', 'LLM_ERROR', 'CONTEXT_ERROR', 'DATABASE_ERROR', 'QUERY_TIMEOUT', 'CONVERSATION_CONFLICT']);

export function Chat({ user, onExpired }: { user: Identity; onExpired: () => void }) {
  const [mode, setMode] = useState<Mode>('query');
  const [drafts, setDrafts] = useState<Record<Mode, string>>({ query: '', analysis: '' });
  const [records, setRecords] = useState<Record<Mode, Entry[]>>({ query: [], analysis: [] });
  const [conversation, setConversation] = useState<string>();
  const [blocked, setBlocked] = useState(false);
  const [pending, setPending] = useState(false);
  const current = useRef(0);
  const inFlight = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const draft = drafts[mode]; const entries = records[mode];
  useEffect(() => () => { current.current++; controller.current?.abort(); inFlight.current = false; }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [entries, pending, mode]);
  function updateEntry(target: Mode, entryId: number, patch: Partial<Entry>) {
    setRecords(all => ({ ...all, [target]: all[target].map(item => item.id === entryId ? { ...item, ...patch } : item) }));
  }

  async function send(retry?: Entry) {
    const question = retry?.question ?? draft.trim();
    const target = mode;
    if (!question || inFlight.current || (target === 'query' && blocked) || !user.permissions.includes('query.execute')) return;
    const id = ++current.current;
    const entryId = retry?.id ?? id;
    const runId = target === 'analysis' ? retry?.runId ?? crypto.randomUUID() : undefined;
    const abort = new AbortController(); controller.current = abort;
    inFlight.current = true; setPending(true);
    if (retry) updateEntry(target, entryId, { error: undefined, uncertain: false, retryable: false });
    else {
      setDrafts(all => ({ ...all, [target]: '' }));
      setRecords(all => ({ ...all, [target]: [...all[target], { id: entryId, question, runId }] }));
    }
    const timer = window.setTimeout(() => abort.abort(), target === 'query' ? 180000 : 1200000);
    let traceId = '';
    try {
      const body = target === 'analysis' ? { question, mode: target, analysis_run_id: runId }
        : { question, mode: target, ...(conversation ? { conversation_id: conversation } : {}) };
      const value = await request('/api/v1/query', body, user.user_id, abort.signal, value => { traceId = value; });
      if (id !== current.current) return;
      if (target === 'query') {
        const result = queryResult(value); setConversation(result.conversation_id);
        updateEntry(target, entryId, { result, requestId: result.request_id, traceId });
      } else {
        const analysis = analysisResult(value, runId!);
        updateEntry(target, entryId, { analysis, requestId: analysis.request_id, traceId });
      }
    } catch (err) {
      if (id !== current.current) return;
      if (err instanceof APIError && err.status === 401) { onExpired(); return; }
      const definite = err instanceof APIError && definiteErrors.has(err.code);
      if (target === 'query' && (!definite || (err instanceof APIError && err.code === 'CONVERSATION_UNAVAILABLE'))) setBlocked(true);
      const error = definite ? (err as Error).message : target === 'query'
        ? '查询结果未确认，请新建问数对话并补全问题。' : '分析结果未确认，可用原问题和原任务编号手动重试。';
      updateEntry(target, entryId, { error, uncertain: !definite, traceId, requestId: err instanceof APIError ? err.requestId : undefined,
        retryable: target === 'analysis' && (!definite || (err instanceof APIError && retryableErrors.has(err.code))) });
    } finally {
      window.clearTimeout(timer);
      if (id === current.current) { inFlight.current = false; setPending(false); controller.current = null; }
    }
  }
  function newDialogue() {
    if (inFlight.current) return;
    current.current++; setRecords(all => ({ ...all, query: [] })); setConversation(undefined);
    setBlocked(false); setDrafts(all => ({ ...all, query: '' }));
  }
  function switchMode(target: Mode) { if (!inFlight.current) setMode(target); }
  return <div className="chat-layout">
    <aside className="sidebar"><div className="section-label">工作空间</div>
      <button className={mode === 'query' ? 'mode-selected' : 'mode-button'} aria-pressed={mode === 'query'} disabled={pending} onClick={() => switchMode('query')}>问数</button>
      <button className={mode === 'analysis' ? 'mode-selected' : 'mode-button'} aria-pressed={mode === 'analysis'} disabled={pending} onClick={() => switchMode('analysis')}>经营分析</button>
      <p>{mode === 'query' ? '从完整问题开始，再围绕上次成功结果继续追问。' : '请明确指标和两个时期。分析不会继承问数条件，每个问题独立执行。'}</p>
      {mode === 'query' && <button className="secondary" disabled={pending} onClick={newDialogue}>新建问数对话</button>}
      <div className="scope-note">刷新会清空当前对话展示，登录状态仍按会话期限保留。<br/>有查询权限的账号共享当前销售数据。</div>
    </aside>
    <section className="chat"><div className="chat-top"><h1>{mode === 'query' ? '问数' : '经营分析'}</h1>
      <span>{mode === 'query' ? '用自然语言查询销售数据' : '两期人民币净销售额 / 毛利 · 产品因素归因'}</span></div>
      <div className="timeline" aria-live="polite">
        {!entries.length && <section className="welcome"><div className="welcome-mark">BI</div><h2>从一个经营问题开始</h2>
          <p>{mode === 'query' ? '例如：2025年2月的人民币净销售额是多少？' : '例如：分析2025年2月相比2025年1月的人民币毛利变化。'}</p>
          <p>{mode === 'query' ? '结果可继续追问，SQL 可展开查看。' : '请提供完整问题；当前支持产品因素归因。'}</p></section>}
        {entries.map(item => <article className="turn" key={item.id}>
          <div className="question"><span>你</span><p>{item.question}</p></div>
          {item.result && <div className="answer"><span className="answer-label">ChatBI</span><ResultView data={item.result}/>
            <details><summary>查看经校验 SQL</summary><pre>{item.result.sql}</pre></details></div>}
          {item.analysis && <div className="answer"><span className="answer-label">ChatBI</span><AnalysisReport result={item.analysis}/></div>}
          {item.error && <div className="answer"><p role="alert">{item.error}</p>
            {item.retryable && <button className="secondary" disabled={pending} onClick={() => void send(item)}>重试原分析</button>}
            {mode === 'analysis' && !item.retryable && <p className="result-meta">当前任务不可按此错误恢复；不会自动创建新任务。</p>}</div>}
          {(item.requestId || item.traceId) && <details className="diagnostics"><summary>查看请求信息</summary>
            {item.requestId && <p>请求编号：{item.requestId}</p>}{item.traceId && <p>链路编号：{item.traceId}</p>}
          </details>}
        </article>)}
        {pending && <p className="loading" role="status">{mode === 'query' ? '正在查询…' : '正在分析…'}</p>}<div ref={end}/>
      </div>
      <div className="composer-wrap">{mode === 'query' && blocked && <p role="alert">请新建问数对话，并重新提供完整问题。</p>}
        <form className="composer" onSubmit={event => { event.preventDefault(); void send(); }}>
          <label className="sr-only" htmlFor="question">问题</label><textarea id="question" value={draft}
            onChange={event => setDrafts(all => ({ ...all, [mode]: event.target.value }))} placeholder="输入问题；等待期间也可以编辑下一条草稿" rows={3}/>
          <div className="composer-actions"><span>分析结果以已校验的数据为依据</span>
            <button disabled={pending || (mode === 'query' && blocked) || !draft.trim() || !user.permissions.includes('query.execute')}>发送</button></div>
        </form>
      </div>
    </section>
  </div>;
}
