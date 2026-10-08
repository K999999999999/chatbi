import { useEffect, useRef, useState } from 'react';
import { APIError, request, type Identity } from './api';

type Status = 'ready' | 'not_ready' | 'unknown';
type View = { status: Status; details?: { dependencies: Record<string, Status>; model: { status: string }; capacity?: { business?: { active: number; max_total: number }; export?: { active: number; max_total: number } }; backup?: { overdue?: boolean; failure_code?: string; last_success?: string } } };
const dependencyNames: Record<string, string> = { control_database: '应用数据库', business_database: '业务数据库', qdrant: '检索服务', assets: '业务与检索资产' };
const stateNames = { ready: '可用', not_ready: '不可用', unknown: '未确认' };

const backupFailures: Record<string, string> = {
  BACKUP_FAILED: '备份失败，请检查本机日志', BACKUP_LOCKED: '另一个本机操作正在执行',
  BACKUP_KEY_UNAVAILABLE: '备份密钥未初始化或不可用', BACKUP_STORAGE_UNAVAILABLE: '备份目录或工具不可用',
  BACKUP_TIMEOUT: '备份超时', BACKUP_INVALID: '备份校验失败',
};

export function OperationsStatus({ user, onExpired }: { user: Identity; onExpired: () => void }) {
  const [view, setView] = useState<View | null>(null);
  const expired = useRef(onExpired); expired.current = onExpired;
  useEffect(() => {
    let stopped = false; let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function refresh() {
      try {
        const response = await request('/api/v1/operations/status', undefined, user.user_id,
          AbortSignal.any([controller.signal, AbortSignal.timeout(8000)])) as View;
        if (!response || !['ready', 'not_ready', 'unknown'].includes(response.status)) throw new Error('状态响应无效');
        if (!stopped) setView(response);
      } catch (err) {
        if (stopped) return;
        setView(null);
        if (err instanceof APIError && err.status === 401) { stopped = true; expired.current(); return; }
      }
      if (!stopped) timer = setTimeout(() => void refresh(), 10000);
    }
    void refresh();
    return () => { stopped = true; clearTimeout(timer); controller.abort(); };
  }, [user.user_id]);
  const details = view?.details;
  const lastSuccess = details?.backup?.last_success;
  const lastBackupAt = typeof lastSuccess === 'string' && /^[0-9TZ:+.\-]{20,40}$/.test(lastSuccess) && Number.isFinite(Date.parse(lastSuccess))
    ? new Date(lastSuccess).toLocaleString() : null;
  const failureCode = details?.backup?.failure_code;
  const backupFailure = typeof failureCode === 'string' && Object.hasOwn(backupFailures, failureCode) ? backupFailures[failureCode] : null;
  return <aside aria-label="运行状态" className="operations-status">
    {view?.status !== 'ready' && <p role="status">{view ? '服务暂时不可用，请稍后重试' : '服务连接状态未确认'}</p>}
    {details && <details><summary>运行状态：{stateNames[view!.status]}</summary>
      <ul>{Object.entries(dependencyNames).map(([key, name]) => <li key={key}>{name}：{stateNames[details.dependencies?.[key]] ?? '未确认'}</li>)}
        <li>模型：{details.model?.status === 'success' ? '最近调用成功' : details.model?.status === 'failure' ? '最近调用失败' : '无近期调用证据'}</li>
        <li>业务执行：{Number.isSafeInteger(details.capacity?.business?.active) ? `${details.capacity!.business!.active} / ${details.capacity!.business!.max_total}` : '未确认'}</li>
        <li>导出执行：{Number.isSafeInteger(details.capacity?.export?.active) ? `${details.capacity!.export!.active} / ${details.capacity!.export!.max_total}` : '未确认'}</li>
        <li>备份：{!lastBackupAt ? '尚无成功备份证据' : details.backup?.overdue ? '已超过24小时，请检查' : details.backup?.failure_code ? '最近备份失败，请检查' : '有成功备份证据'}</li>
        {lastBackupAt && <li>最近成功备份：{lastBackupAt}</li>}
        {backupFailure && <li>备份提示：{backupFailure}</li>}
      </ul>
    </details>}
  </aside>;
}
