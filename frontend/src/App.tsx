import { Chat } from './Chat';
import { useEffect, useRef, useState } from 'react';
import { APIError, identity, request, type Identity } from './api';

export default function App() {
  const [user, setUser] = useState<Identity | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const epoch = useRef(0);
  const channel = useRef<BroadcastChannel | null>(null);
  const clear = () => { epoch.current++; setUser(null); setPassword(''); setNewPassword(''); setBusy(false); };

  useEffect(() => {
    const pending = location.hash.startsWith('#logout-pending=');
    const current = epoch.current;
    if (pending) { setError('退出尚未确认，请重试退出或明确重新登录。'); setReady(true); }
    else request('/auth/browser/me', undefined, undefined, AbortSignal.timeout(30000))
      .then(value => { if (current === epoch.current) setUser(identity(value)); })
      .catch(err => { if (current === epoch.current && !(err instanceof APIError && err.status === 401)) setError(String(err.message)); })
      .finally(() => { if (current === epoch.current) setReady(true); });
    channel.current = new BroadcastChannel('chatbi-identity');
    channel.current.onmessage = event => {
      if (event.data.kind === 'logout') location.hash = `logout-pending=${event.data.userId}`;
      clear(); setBusy(false); setError('登录状态已在另一个页面变化，请重新登录。');
    };
    return () => { epoch.current++; channel.current?.close(); };
  }, []);

  async function login() {
    if (busy) return;
    setBusy(true); setError('');
    const current = ++epoch.current;
    try {
      const value = identity(await request('/auth/browser/login', { username, password }, undefined, AbortSignal.timeout(30000)));
      if (current !== epoch.current) return;
      setUser(value); setPassword(''); history.replaceState(null, '', location.pathname);
      channel.current?.postMessage({ kind: 'login' });
    } catch (err) { if (current === epoch.current) setError((err as Error).message); }
    finally { if (current === epoch.current) setBusy(false); }
  }

  async function logout() {
    const id = user?.user_id ?? Number(location.hash.split('=')[1]);
    location.hash = `logout-pending=${id}`; clear(); setBusy(true); setError('');
    const current = epoch.current;
    channel.current?.postMessage({ kind: 'logout', userId: id });
    try {
      await request('/auth/browser/logout', {}, id, AbortSignal.timeout(30000));
      if (current === epoch.current) { history.replaceState(null, '', location.pathname); setError('已退出登录。'); }
    } catch { if (current === epoch.current) setError('退出尚未确认，请重试退出或明确重新登录。'); }
    finally { if (current === epoch.current) setBusy(false); }
  }

  async function changePassword() {
    if (!user || busy) return;
    setBusy(true); setError('');
    const current = epoch.current;
    try {
      await request('/auth/browser/change-password', { current_password: password, new_password: newPassword }, user.user_id, AbortSignal.timeout(30000));
      if (current === epoch.current) { clear(); setError('密码已修改，请重新登录。'); channel.current?.postMessage({ kind: 'login' }); }
    } catch (err) { if (current === epoch.current) { if (err instanceof APIError && err.status === 401) clear(); setError((err as Error).message); } }
    finally { if (current === epoch.current) setBusy(false); }
  }

  if (!ready) return <main className="auth"><p>正在核验登录状态…</p></main>;
  if (!user || user.must_change_password) return <main className="auth"><section className="auth-card">
    <div className="brand">ChatBI</div><h1>{user ? '首次登录，请修改密码' : '销售经营分析'}</h1>
    <p>用对话探索数据，依据事实理解经营变化。</p>
    <form onSubmit={e => { e.preventDefault(); void (user ? changePassword() : login()); }}>
      {!user && <label>账号<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required disabled={busy}/></label>}
      <label>{user ? '当前密码' : '密码'}<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required disabled={busy}/></label>
      {user && <label>新密码<input type="password" autoComplete="new-password" value={newPassword} onChange={e => setNewPassword(e.target.value)} minLength={12} required disabled={busy}/></label>}
      <button disabled={busy}>{busy ? '正在处理…' : user ? '修改密码' : '登录'}</button>
    </form>
    {location.hash.startsWith('#logout-pending=') && <button className="secondary" disabled={busy} onClick={() => void logout()}>重试退出</button>}
    {user && <button className="secondary" onClick={() => void logout()}>退出登录</button>}
    {error && <p role="alert">{error}</p>}
  </section></main>;
  return <main className="workspace"><header><div className="brand">ChatBI <span>销售经营分析</span></div><div>{user.username} <button className="secondary" onClick={() => void logout()}>退出登录</button></div></header><Chat key={user.user_id} user={user} onExpired={() => { clear(); setError("登录已失效，请重新登录。"); }}/></main>;
}
