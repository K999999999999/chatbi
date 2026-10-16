import { test, expect } from '@playwright/test';
import { isFinalExecutionResponse, login } from './helpers';

const id = '00000000-0000-4000-8000-000000000001';
const tid = '00000000-0000-4000-8000-000000000002';
const header = { id, kind: 'query', title: '已保存的问数', first_question: '销售额', context_revision: 1,
  record_revision: 2, active: false, can_continue: true, can_resume: false, last_success_turn_id: tid, analysis_run_id: null };
const turn = { id: tid, history_id: id, ordinal: 1, question: '销售额', status: 'succeeded', public_error: null,
  snapshot: { request_id: 'saved-r', sql: 'SELECT 12', columns: ['销售额'], rows: [['12.50']], row_count: 1, truncated: false } };

type RequeryRecovery = 'late-acceptance' | 'definite-rejection' | 'retry-401' | 'retry-403' | 'logout' | 'account-switch';

async function verifyUncertainRequery(page: import('@playwright/test').Page,
  origin: 'query-history' | 'analysis-history' | 'saved-result', recovery: RequeryRecovery = 'late-acceptance',
  context?: import('@playwright/test').BrowserContext) {
  const sourceHistoryId = '00000000-0000-4000-8000-000000000061';
  const sourceTurnId = '00000000-0000-4000-8000-000000000062';
  const savedResultId = '00000000-0000-4000-8000-000000000063';
  const nextHistoryId = '00000000-0000-4000-8000-000000000064';
  const nextTurnId = '00000000-0000-4000-8000-000000000065';
  const executionId = '00000000-0000-4000-8000-000000000066';
  const kind = origin === 'analysis-history' ? 'analysis' : 'query';
  const sourceHeader = { ...header, id: sourceHistoryId, kind,
    title: origin === 'analysis-history' ? '失败的历史分析' : '历史问数',
    first_question: origin === 'analysis-history' ? '分析原问题' : '销售额',
    last_success_turn_id: origin === 'analysis-history' ? null : sourceTurnId,
    analysis_run_id: origin === 'analysis-history' ? '00000000-0000-4000-8000-000000000067' : null };
  const sourceTurn = origin === 'analysis-history'
    ? { id: sourceTurnId, history_id: sourceHistoryId, ordinal: 1, question: '分析原问题', status: 'failed',
      public_error: { error_message: '原分析失败，保留原状态' } }
    : { ...turn, id: sourceTurnId, history_id: sourceHistoryId };
  const saved = { id: savedResultId, kind: 'query', title: '固定成果', record_revision: 0,
    source_history_id: sourceHistoryId, source_turn_id: sourceTurnId, snapshot: turn.snapshot };
  const nextHeader = { ...sourceHeader, id: nextHistoryId, title: '重新查询结果', active: false,
    last_success_turn_id: nextTurnId, active_turn_id: null };
  const acceptedTurn = { id: nextTurnId, history_id: nextHistoryId, ordinal: 1,
    question: sourceTurn.question, status: 'accepted', public_error: null, execution_id: executionId };
  const completedTurn = { ...acceptedTurn, status: 'succeeded' };
  const attempts: { path: string; body: Record<string, unknown> }[] = [];
  const operationLookups: string[] = [];
  const observedExecutions: string[] = [];

  await page.route('**/api/v1/histories**', async route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/v1/histories' && route.request().method() === 'GET') {
      return route.fulfill({ json: { items: [sourceHeader], next_cursor: null } });
    }
    if (url.pathname === `/api/v1/histories/${sourceHistoryId}`) return route.fulfill({ json: sourceHeader });
    if (url.pathname === `/api/v1/histories/${sourceHistoryId}/turns`) {
      return route.fulfill({ json: { items: [sourceTurn], next_cursor: null } });
    }
    if (url.pathname === `/api/v1/histories/${sourceHistoryId}/turns/${sourceTurnId}`) {
      return route.fulfill({ json: sourceTurn });
    }
    return route.continue();
  });
  await page.route('**/api/v1/saved-results**', async route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/v1/saved-results' && route.request().method() === 'GET') {
      return route.fulfill({ json: { items: [saved], next_cursor: null } });
    }
    if (url.pathname === `/api/v1/saved-results/${savedResultId}`) return route.fulfill({ json: saved });
    return route.continue();
  });
  await page.route('**/api/v1/**/requery-executions', async route => {
    const request = route.request();
    attempts.push({ path: new URL(request.url()).pathname, body: request.postDataJSON() as Record<string, unknown> });
    if (attempts.length === 2 && recovery === 'definite-rejection') {
      return route.fulfill({ status: 422, json: { request_id: 'rejected', error_code: 'INVALID_REQUEST', error_message: '请求已明确拒绝' } });
    }
    if (attempts.length === 2 && recovery === 'retry-401') {
      return route.fulfill({ status: 401, json: { request_id: 'expired', error_code: 'AUTHENTICATION_REQUIRED', error_message: '会话已失效' } });
    }
    if (attempts.length === 2 && recovery === 'retry-403') {
      return route.fulfill({ status: 403, json: { request_id: 'forbidden', error_code: 'AUTHORIZATION_DENIED', error_message: '无权访问' } });
    }
    return route.abort('failed');
  });
  await page.route('**/api/v1/executions/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.includes('/by-operation/')) {
      operationLookups.push(path.split('/').at(-1)!);
      if (recovery === 'retry-401' || recovery === 'retry-403') {
        return route.fulfill({ status: 503, json: { request_id: 'temporary', error_code: 'TEMPORARY', error_message: '暂时无法查询受理状态' } });
      }
      if (operationLookups.length > 1) return route.fulfill({ json: {
        execution: { id: executionId, history_id: nextHistoryId, turn_id: nextTurnId,
          operation_id: String(attempts.at(-1)!.body.operation_id), mode: kind,
          operation_kind: 'saved_result_requery', status: 'accepted' },
        history: nextHeader, turn: acceptedTurn,
      } });
      return route.fulfill({ status: 503, json: { request_id: 'temporary', error_code: 'TEMPORARY', error_message: '暂时无法查询受理状态' } });
    }
    if (path.endsWith('/events')) {
      observedExecutions.push(path.split('/').at(-2)!);
      const base = { version: 1, execution_id: executionId, history_id: nextHistoryId,
        turn_id: nextTurnId, draft_generation: 0 };
      const frame = (sequence: number, type: string, payload: Record<string, unknown>) =>
        `id: ${sequence}\nevent: ${type}\ndata: ${JSON.stringify({ ...base, sequence, type, payload })}\n\n`;
      return route.fulfill({ status: 200, contentType: 'text/event-stream', body:
        frame(0, 'snapshot', { status: 'running', stage: null, completed_tasks: 0, total_tasks: null,
          stop_reason: null, draft_generation: 0, draft: null })
        + frame(1, 'terminal', { status: 'succeeded' }) });
    }
    if (path === `/api/v1/executions/${executionId}`) {
      observedExecutions.push(path.split('/').at(-1)!);
      return route.fulfill({ json: { execution: { id: executionId, status: 'succeeded' }, history: nextHeader, turn: completedTurn } });
    }
    return route.continue();
  });

  await login(page);
  await page.goto(origin === 'saved-result' ? `/#saved=${savedResultId}` : `/#history=${sourceHistoryId}`);
  if (origin === 'analysis-history') await expect(page.getByText('原分析失败，保留原状态', { exact: true })).toBeVisible();
  else await expect(page.getByText('12.50', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: origin === 'analysis-history' ? '重新分析当前数据' : '重新查询当前数据', exact: true }).click();
  const uncertainAlert = page.locator('p[role="alert"]').filter({ hasText: '受理结果暂未确认。可明确重试同一请求；本请求不会自动重发。' });
  await expect(uncertainAlert).toBeVisible();
  await expect(uncertainAlert.getByRole('button', { name: '明确重试同一请求' })).toBeVisible();
  expect(attempts).toHaveLength(1);
  if (origin === 'analysis-history') await expect(page.getByText('原分析失败，保留原状态', { exact: true })).toBeVisible();
  else await expect(page.getByText('12.50', { exact: true })).toBeVisible();

  if (recovery === 'retry-401' || recovery === 'retry-403') {
    await uncertainAlert.getByRole('button', { name: '明确重试同一请求' }).click();
    expect(attempts).toHaveLength(2);
    expect(attempts[1]).toEqual(attempts[0]);
    if (recovery === 'retry-401') await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
    else await expect(page.getByRole('alert').filter({ hasText: '当前账号已无权查看这些记录' })).toBeVisible();
    await expect(page.getByRole('button', { name: '明确重试同一请求' })).toHaveCount(0);
    await expect(page.getByText('12.50', { exact: true })).toHaveCount(0);
    return;
  }
  if (recovery === 'logout') {
    await page.getByRole('button', { name: '退出登录', exact: true }).click();
    await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '明确重试同一请求' })).toHaveCount(0);
    await expect(page.getByText('12.50', { exact: true })).toHaveCount(0);
    return;
  }
  if (recovery === 'account-switch') {
    if (!context) throw new Error('账号切换测试需要BrowserContext');
    const other = await context.newPage();
    await other.goto('/');
    await other.getByRole('button', { name: '退出登录' }).click();
    await login(other, 'other-user');
    await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '明确重试同一请求' })).toHaveCount(0);
    await expect(page.getByText('12.50', { exact: true })).toHaveCount(0);
    await other.close();
    return;
  }

  const completed = page.waitForResponse(isFinalExecutionResponse);
  await uncertainAlert.getByRole('button', { name: '明确重试同一请求' }).click();
  if (recovery === 'definite-rejection') {
    await expect(uncertainAlert).toHaveCount(0);
    await expect(page.getByRole('alert').filter({ hasText: '请求已明确拒绝' })).toBeVisible();
    await expect(page.getByText('12.50', { exact: true })).toBeVisible();
    expect(attempts).toHaveLength(2);
    expect(attempts[1]).toEqual(attempts[0]);
    await page.getByRole('button', { name: '重新查询当前数据', exact: true }).click();
  }
  await completed;
  await expect.poll(() => attempts.length).toBe(recovery === 'definite-rejection' ? 3 : 2);
  if (recovery === 'definite-rejection') {
    expect(attempts[1]).toEqual(attempts[0]);
    expect(attempts[2].path).toBe(attempts[0].path);
    expect(attempts[2].body.operation_id).not.toBe(attempts[0].body.operation_id);
  } else expect(attempts[1]).toEqual(attempts[0]);
  expect(attempts[0].path).toBe(origin === 'saved-result'
    ? `/api/v1/saved-results/${savedResultId}/requery-executions`
    : `/api/v1/histories/${sourceHistoryId}/requery-executions`);
  expect(attempts[0].body.operation_id).toMatch(/^[0-9a-f-]{36}$/);
  expect(attempts[0].body.source_turn_id).toBe(origin === 'query-history' ? sourceTurnId : undefined);
  expect(operationLookups).toEqual(recovery === 'definite-rejection'
    ? [attempts[0].body.operation_id, attempts[2].body.operation_id]
    : [attempts[0].body.operation_id, attempts[0].body.operation_id]);
  expect(observedExecutions.length).toBeGreaterThan(0);
  expect(observedExecutions.every(id => id === executionId)).toBe(true);
  await expect(page).toHaveURL(new RegExp(`#history=${nextHistoryId}$`));
  await expect(page.getByRole('button', { name: '明确重试同一请求' })).toHaveCount(0);
}

test('刷新按URL读取已保存快照，不触发执行', async ({ page }) => {
  let writes = 0;
  await page.route('**/auth/browser/me', route => route.fulfill({ json: { user_id: 1, username: 'analyst', permissions: ['query.execute'], must_change_password: false } }));
  await page.route('**/api/v1/operations/status', route => route.fulfill({ json: {
    version: 1, status: 'ready', checked_at: null, query_available: true, message: '',
  } }));
  await page.route('**/api/v1/histories**', route => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() !== 'GET') writes++;
    const value = path.endsWith(`/turns/${tid}`) ? turn : path.endsWith('/turns')
      ? { items: [{ ...turn, snapshot: undefined }], next_cursor: null } : path.endsWith(id) ? header : { items: [header], next_cursor: null };
    return route.fulfill({ json: value });
  });
  await page.goto(`/#history=${id}`);
  await expect(page.getByText('12.50', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText('12.50', { exact: true })).toBeVisible();
  expect(writes).toBe(0);
});

test('另存副本、独立重命名、删除来源与成果、显式重查创建新历史', async ({ page }) => {
  const { login, send } = await import('./helpers');
  let executions = 0;
  page.on('request', req => { if (req.method() === 'POST' && (req.url().endsWith('/executions') || req.url().endsWith('/requery-executions'))) executions++; });
  await login(page);
  await send(page, '历史管理测试销售额');
  await expect(page.getByRole('table')).toBeVisible();
  const sourceUrl = page.url();
  await page.getByRole('button', { name: '另存成果', exact: true }).click();
  await page.getByLabel('成果名称').fill('固定成果甲');
  await page.getByRole('button', { name: '保存名称', exact: true }).click();
  await expect(page.getByText('已保存。', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '已保存成果', exact: true }).click();
  await page.getByRole('button', { name: '问数 · 固定成果甲', exact: true }).click();
  await expect(page.getByRole('heading', { name: '固定成果甲', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '重命名', exact: true }).click();
  await page.getByLabel('记录名称').fill('固定成果乙');
  await page.getByRole('button', { name: '保存名称', exact: true }).click();
  await expect(page.getByRole('heading', { name: '固定成果乙', exact: true })).toBeVisible();
  await page.goto(sourceUrl);
  await expect(page.getByRole('table')).toBeVisible();
  page.on('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: '删除历史', exact: true }).click();
  await expect(page.getByRole('table')).toHaveCount(0);
  await page.getByRole('button', { name: '已保存成果', exact: true }).click();
  await page.getByRole('button', { name: '问数 · 固定成果乙', exact: true }).click();
  await expect(page.getByRole('table')).toBeVisible();
  expect(executions).toBe(1);
  await page.getByRole('button', { name: '重新查询当前数据', exact: true }).click();
  await expect(page.getByRole('button', { name: '另存成果', exact: true })).toBeVisible();
  expect(page.url()).not.toBe(sourceUrl);
  expect(executions).toBe(2);
  await page.getByRole('button', { name: '已保存成果', exact: true }).click();
  await page.getByRole('button', { name: '问数 · 固定成果乙', exact: true }).click();
  await page.getByRole('button', { name: '删除成果', exact: true }).click();
  await page.getByRole('button', { name: '历史记录', exact: true }).click();
  await expect(page.getByRole('button', { name: /問数|问数 · 固定成果/ })).toBeVisible();
});

test('执行下一轮时可另存旧成功结果，且不丢失下一轮交付', async ({ page }) => {
  const { login, send } = await import('./helpers');
  await login(page); await send(page, '允许另存旧结果');
  await expect(page.getByRole('table')).toBeVisible();
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/v1/histories/*/executions', async route => { await held; await route.continue(); });
  await send(page, '改成毛利');
  await expect(page.getByRole('status')).toBeVisible();
  await page.getByRole('button', { name: '另存成果', exact: true }).click();
  await page.getByLabel('成果名称').fill('执行期间副本');
  await page.getByRole('button', { name: '保存名称', exact: true }).click();
  await expect(page.getByText('已保存。', { exact: true })).toBeVisible();
  release();
  await expect(page.getByRole('table')).toHaveCount(2);
  await expect(page.getByRole('button', { name: '发送', exact: true })).toBeDisabled();
});

for (const origin of ['query-history', 'analysis-history', 'saved-result'] as const) {
  test(`重查受理与首次状态查询都失败时保留${origin}来源和原操作`, async ({ page }) => {
    await verifyUncertainRequery(page, origin);
  });
}

test('重查明确拒绝后允许用户另行发起新操作', async ({ page }) => {
  await verifyUncertainRequery(page, 'saved-result', 'definite-rejection');
});

for (const status of [401, 403] as const) {
  test(`未确认重查显式恢复遇到${status}时清除私有状态`, async ({ page }) => {
    await verifyUncertainRequery(page, 'saved-result', status === 401 ? 'retry-401' : 'retry-403');
  });
}

test('退出登录清除未确认重查操作和原成果', async ({ page }) => {
  await verifyUncertainRequery(page, 'saved-result', 'logout');
});

test('切换账号清除未确认重查操作和原成果', async ({ page, context }) => {
  await verifyUncertainRequery(page, 'saved-result', 'account-switch', context);
});
