import { useEffect, useRef, useState } from 'react';
import { APIError, request, type Identity } from './api';
import { queryResult, ResultTable, type QueryResult } from './results';

type Entry = { id: number; question: string; result?: QueryResult; error?: string; uncertain?: boolean };
const definiteErrors = new Set(['INVALID_REQUEST', 'AUTHORIZATION_DENIED', 'AUTHENTICATION_UNAVAILABLE',
  'CANNOT_ANSWER', 'SQL_REJECTED', 'LLM_ERROR', 'CONTEXT_ERROR', 'DATABASE_ERROR', 'QUERY_TIMEOUT',
  'CONVERSATION_UNAVAILABLE', 'CLARIFICATION_REQUIRED', 'UNSUPPORTED_ANALYSIS', 'CONVERSATION_CONFLICT']);

export function Chat({ user, onExpired }: { user: Identity; onExpired: () => void }) {
  const [draft, setDraft] = useState('');
  const [entries, setEntries] = useState<Entry[]>([]);
  const [conversation, setConversation] = useState<string>();
  const [blocked, setBlocked] = useState(false);
  const [pending, setPending] = useState(false);
  const current = useRef(0);
  const inFlight = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => () => { current.current++; controller.current?.abort(); inFlight.current = false; }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [entries, pending]);

  async function send() {
    const question = draft.trim();
    if (!question || inFlight.current || blocked) return;
    const id = ++current.current;
    const abort = new AbortController(); controller.current = abort;
    inFlight.current = true; setPending(true); setDraft('');
    setEntries(items => [...items, { id, question }]);
    const timer = window.setTimeout(() => abort.abort(), 180000);
    try {
      const result = queryResult(await request('/api/v1/query', { question, mode: 'query',
        ...(conversation ? { conversation_id: conversation } : {}) }, user.user_id, abort.signal));
      if (id !== current.current) return;
      setConversation(result.conversation_id);
      setEntries(items => items.map(item => item.id === id ? { ...item, result } : item));
    } catch (err) {
      if (id !== current.current) return;
      if (err instanceof APIError && err.status === 401) { onExpired(); return; }
      const definite = err instanceof APIError && definiteErrors.has(err.code);
      if (!definite || (err instanceof APIError && err.code === 'CONVERSATION_UNAVAILABLE')) setBlocked(true);
      const error = definite ? (err as Error).message : '查询结果未确认，请新建问数对话并补全问题。';
      setEntries(items => items.map(item => item.id === id ? { ...item, error, uncertain: !definite } : item));
    } finally {
      window.clearTimeout(timer);
      if (id === current.current) { inFlight.current = false; setPending(false); controller.current = null; }
    }
  }
  function newDialogue() {
    if (inFlight.current) return;
    current.current++; setEntries([]); setConversation(undefined); setBlocked(false); setDraft('');
  }
  return <div className="chat-layout">
    <aside className="sidebar"><div className="section-label">工作空间</div><div className="mode-selected">问数</div>
      <p>从完整问题开始，再围绕上次成功结果继续追问。</p>
      <button className="secondary" disabled={pending} onClick={newDialogue}>新建问数对话</button>
      <div className="scope-note">当前支持销售数据问数。刷新会清空当前对话展示，登录状态仍按会话期限保留。</div>
    </aside>
    <section className="chat"><div className="chat-top"><h1>问数</h1><span>用自然语言查询销售数据</span></div>
      <div className="timeline" aria-live="polite">
        {!entries.length && <section className="welcome"><div className="welcome-mark">BI</div><h2>从一个经营问题开始</h2>
          <p>例如：2025年2月的人民币净销售额是多少？</p><p>有查询权限的账号共享当前销售数据。</p></section>}
        {entries.map(item => <article className="turn" key={item.id}>
          <div className="question"><span>你</span><p>{item.question}</p></div>
          {item.result && <div className="answer"><span className="answer-label">ChatBI</span><ResultTable data={item.result}/>
            <details><summary>查看经校验 SQL</summary><pre>{item.result.sql}</pre></details></div>}
          {item.error && <div className="answer"><p role="alert">{item.error}</p></div>}
        </article>)}
        {pending && <p className="loading" role="status">正在查询…</p>}<div ref={end}/>
      </div>
      <div className="composer-wrap">{blocked && <p role="alert">请新建问数对话，并重新提供完整问题。</p>}
        <form className="composer" onSubmit={event => { event.preventDefault(); void send(); }}>
          <label className="sr-only" htmlFor="question">问题</label><textarea id="question" value={draft} onChange={event => setDraft(event.target.value)}
            placeholder="输入问题；查询期间也可以编辑下一条草稿" rows={3}/>
          <div className="composer-actions"><span>分析结果以已校验的数据为依据</span><button disabled={pending || blocked || !draft.trim() || !user.permissions.includes('query.execute')}>发送</button></div>
        </form>
      </div>
    </section>
  </div>;
}
