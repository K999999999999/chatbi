import { useEffect, useRef, useState } from 'react';
import { APIError, request, type Identity } from './api';
import { historyHeader, pageItems, savedResult, type HistoryHeader, type SavedResult } from './history';

export function HistoryPanel({ user, pending, refresh, clearPrivateVersion, onExpired, onForbidden, onOpen, onSaved }: {
  user: Identity; pending: boolean; refresh: number; clearPrivateVersion: number; onExpired: () => void; onForbidden: () => void;
  onOpen: (id: string) => void; onSaved: (id: string) => void;
}) {
  const [tab, setTab] = useState<'histories' | 'saved-results'>('histories');
  const [kind, setKind] = useState(''); const [search, setSearch] = useState(''); const [q, setQ] = useState('');
  const [items, setItems] = useState<(HistoryHeader | SavedResult)[]>([]);
  const [cursor, setCursor] = useState<string | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const epoch = useRef(0);
  const lastClearVersion = useRef(clearPrivateVersion);
  const suppressNextLoad = useRef(false);
  function clearPrivateState(message: string) {
    const filtersChanged = !!(search || q || kind);
    if (filtersChanged) suppressNextLoad.current = true;
    epoch.current++; setItems([]); setCursor(null); setBusy(false); setError(message);
    setSearch(''); setQ(''); setKind('');
  }
  async function load(next?: string) {
    const version = ++epoch.current; setBusy(true); setError('');
    try {
      const params = new URLSearchParams({ q, ...(kind ? { kind } : {}), ...(next ? { cursor: next } : {}) });
      const result = pageItems(await request(`/api/v1/${tab}?${params}`, undefined, user.user_id, AbortSignal.timeout(30000)));
      if (version !== epoch.current) return;
      const decoded = result.items.map(value => tab === 'histories' ? historyHeader(value) : savedResult(value));
      setItems(old => next ? [...old, ...decoded] : decoded); setCursor(result.next_cursor as string | null);
    } catch (err) { if (version === epoch.current) {
      if (err instanceof APIError && err.status === 401) onExpired();
      else if (err instanceof APIError && err.status === 403) onForbidden();
      else setError((err as Error).message);
    } }
    finally { if (version === epoch.current) setBusy(false); }
  }
  useEffect(() => {
    if (lastClearVersion.current === clearPrivateVersion) return;
    lastClearVersion.current = clearPrivateVersion;
    clearPrivateState('');
  }, [clearPrivateVersion]);
  useEffect(() => {
    if (suppressNextLoad.current) {
      suppressNextLoad.current = false; setItems([]); setCursor(null); setBusy(false);
      return () => { epoch.current++; };
    }
    setItems([]); setCursor(null); void load(); return () => { epoch.current++; };
  }, [tab, kind, q, refresh]);
  return <section className="history-panel" aria-label="私人记录">
    <div className="history-tabs"><button aria-pressed={tab === 'histories'} disabled={pending} onClick={() => setTab('histories')}>历史记录</button>
      <button aria-pressed={tab === 'saved-results'} disabled={pending} onClick={() => setTab('saved-results')}>已保存成果</button></div>
    <label>记录类型<select value={kind} disabled={pending} onChange={e => setKind(e.target.value)}>
      <option value="">全部</option><option value="query">问数</option><option value="analysis">经营分析</option></select></label>
    <form onSubmit={e => { e.preventDefault(); if (search.trim() === q) void load(); else setQ(search.trim()); }}>
      <label>搜索名称<input value={search} maxLength={200} onChange={e => setSearch(e.target.value)} /></label><button disabled={busy}>搜索</button></form>
    {error && <p role="alert">{error}</p>}
    {items.map(item => <button key={item.id} disabled={pending || busy} onClick={() => tab === 'histories' ? onOpen(item.id) : onSaved(item.id)}>
      <span>{item.kind === 'query' ? '问数' : '分析'} · </span>{item.title}</button>)}
    {!items.length && !busy && !error && <p>暂无记录</p>}
    {cursor && <button disabled={busy} onClick={() => void load(cursor)}>更多记录</button>}
  </section>;
}
