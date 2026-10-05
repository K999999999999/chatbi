import { test, expect } from '@playwright/test';
import { login, send } from './helpers';
import { decodeExecutionEvent, reduceExecutionEvent, SSEParser, type ExecutionIdentity } from '../src/execution';

test('SSE任意字节分片推进真实阶段，终态后读取正式历史结果', async ({ page }) => {
  await page.addInitScript(() => {
    const nativeFetch = window.fetch.bind(window);
    type Envelope = { execution: { id: string }; history: { id: string }; turn: { id: string } };
    (window as Window & { __executionIdentity?: Envelope }).__executionIdentity = undefined;
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const response = await nativeFetch(input, init);
      const url = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, location.href);
      if (url.pathname.endsWith('/executions') && init?.method === 'POST' && response.ok) {
        (window as Window & { __executionIdentity?: Envelope }).__executionIdentity = await response.clone().json() as Envelope;
      }
      if (!url.pathname.endsWith('/events')) return response;

      const identity = (window as Window & { __executionIdentity?: Envelope }).__executionIdentity;
      if (!identity) throw new Error('受理响应必须先于事件订阅');
      const base = { version: 1, execution_id: identity.execution.id, history_id: identity.history.id,
        turn_id: identity.turn.id, draft_generation: 0 };
      const frame = (sequence: number, type: string, payload: Record<string, unknown>) =>
        `id: ${sequence}\nevent: ${type}\ndata: ${JSON.stringify({ ...base, sequence, type, payload })}\n\n`;
      const bytes = new TextEncoder().encode(
        frame(0, 'snapshot', { status: 'running', stage: null, completed_tasks: 0, total_tasks: null, stop_reason: null, draft_generation: 0 }) +
        frame(1, 'progress', { stage: 'query_execution', completed_tasks: 0, total_tasks: null }) +
        frame(2, 'terminal', { status: 'succeeded' }),
      );
      const terminalOffset = new TextEncoder().encode(
        frame(0, 'snapshot', { status: 'running', stage: null, completed_tasks: 0, total_tasks: null, stop_reason: null, draft_generation: 0 }) +
        frame(1, 'progress', { stage: 'query_execution', completed_tasks: 0, total_tasks: null }),
      ).length;
      let offset = 0; let delayed = false;
      const body = new ReadableStream<Uint8Array>({
        async pull(controller) {
          if (offset >= terminalOffset && !delayed) { delayed = true; await new Promise(resolve => setTimeout(resolve, 150)); }
          if (offset >= bytes.length) { controller.close(); return; }
          controller.enqueue(bytes.slice(offset, Math.min(bytes.length, offset + 3)));
          offset += 3;
        },
      });
      return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-store' } });
    };
  });
  const submissions: string[] = [];
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/executions')) submissions.push(request.postDataJSON().operation_id);
  });
  await login(page);
  await send(page, '2025年2月净销售额');
  await expect(page.locator('.turn [role="status"]')).toHaveText('执行查询');
  await expect(page.getByRole('table')).toBeVisible();
  expect(submissions).toHaveLength(1);
});

test('刷新及第二个标签页恢复同一执行观察且不重发业务请求', async ({ page, context }) => {
  const historyId = '00000000-0000-4000-8000-000000000011';
  const turnId = '00000000-0000-4000-8000-000000000012';
  const executionId = '00000000-0000-4000-8000-000000000013';
  const operationId = '00000000-0000-4000-8000-000000000014';
  const question = '刷新恢复中的执行';
  const history = { id: historyId, kind: 'query', title: question, first_question: question, created_at: '2026-10-05T00:00:00Z',
    updated_at: '2026-10-05T00:00:00Z', context_revision: 0, record_revision: 1, active: true, can_continue: false,
    can_resume: false, last_success_turn_id: null, active_turn_id: turnId, analysis_run_id: null };
  const turn = { id: turnId, history_id: historyId, ordinal: 1, question, status: 'accepted', public_error: null, execution_id: executionId };
  let submissions = 0; let eventReads = 0;
  await context.route('**/api/v1/histories**', async route => {
    const url = new URL(route.request().url()); const path = url.pathname; const method = route.request().method();
    if (path === '/api/v1/histories' && method === 'POST') return route.fulfill({ status: 201, json: history });
    if (path === `/api/v1/histories/${historyId}/executions` && method === 'POST') {
      submissions++;
      return route.fulfill({ status: 202, json: { execution: { id: executionId, history_id: historyId, turn_id: turnId,
        operation_id: operationId, mode: 'query', operation_kind: 'query', status: 'accepted' }, history, turn } });
    }
    if (path === '/api/v1/histories' && method === 'GET') return route.fulfill({ json: { items: [history], next_cursor: null } });
    if (path === `/api/v1/histories/${historyId}` && method === 'GET') return route.fulfill({ json: history });
    if (path === `/api/v1/histories/${historyId}/turns` && method === 'GET') return route.fulfill({ json: { items: [turn], next_cursor: null } });
    if (path === `/api/v1/histories/${historyId}/turns/${turnId}` && method === 'GET') return route.fulfill({ json: turn });
    return route.continue();
  });
  await context.route('**/api/v1/executions/*/events', async route => {
    eventReads++;
    const event = { version: 1, execution_id: executionId, history_id: historyId, turn_id: turnId, sequence: 0,
      draft_generation: 0, type: 'snapshot', payload: { status: 'running', stage: 'sql_generation', completed_tasks: 0,
        total_tasks: null, stop_reason: null, draft_generation: 0 } };
    return route.fulfill({ status: 200, contentType: 'text/event-stream', body: `id: 0\nevent: snapshot\ndata: ${JSON.stringify(event)}\n\n` });
  });
  await login(page);
  await send(page, question);
  await expect(page.getByRole('status')).toContainText('生成查询');
  await expect.poll(() => eventReads).toBeGreaterThan(0);
  const previousReads = eventReads;
  await page.reload();
  await expect(page.getByRole('status')).toContainText('生成查询');
  await expect.poll(() => eventReads).toBeGreaterThan(previousReads);
  const beforeSecondTab = eventReads;
  const secondTab = await context.newPage();
  await secondTab.goto(`/#history=${historyId}`);
  await expect(secondTab.getByRole('status')).toContainText('生成查询');
  await expect.poll(() => eventReads).toBeGreaterThan(beforeSecondTab);
  expect(submissions).toBe(1);
  await secondTab.close();
});

test('取消按钮发送带 CSRF 标记的请求并持续观察 stopping 状态', async ({ page }) => {
  const historyId = '00000000-0000-4000-8000-000000000021';
  const turnId = '00000000-0000-4000-8000-000000000022';
  const executionId = '00000000-0000-4000-8000-000000000023';
  const question = '可取消的慢查询';
  const history = { id: historyId, kind: 'query', title: question, first_question: question,
    created_at: '2026-10-05T00:00:00Z', updated_at: '2026-10-05T00:00:00Z', context_revision: 0,
    record_revision: 1, active: true, can_continue: false, can_resume: false,
    last_success_turn_id: null, active_turn_id: turnId, analysis_run_id: null };
  const turn = { id: turnId, history_id: historyId, ordinal: 1, question, status: 'accepted',
    public_error: null, execution_id: executionId };
  let cancelBody: unknown; let cancelMarker = ''; let eventReads = 0; let cancelled = false;
  await page.route('**/api/v1/histories**', async route => {
    const url = new URL(route.request().url()); const path = url.pathname; const method = route.request().method();
    if (path === '/api/v1/histories' && method === 'POST') {
      return route.fulfill({ status: 201, json: { ...history, active: false, active_turn_id: null } });
    }
    if (path === `/api/v1/histories/${historyId}/executions` && method === 'POST') {
      return route.fulfill({ status: 202, json: { execution: { id: executionId, history_id: historyId,
        turn_id: turnId, operation_id: '00000000-0000-4000-8000-000000000024', mode: 'query',
        operation_kind: 'query', status: 'accepted', stop_reason: null }, history, turn } });
    }
    return route.continue();
  });
  await page.route('**/api/v1/executions/*/events', async route => {
    eventReads++;
    const event = { version: 1, execution_id: executionId, history_id: historyId, turn_id: turnId,
      sequence: 0, draft_generation: 0, type: 'snapshot', payload: {
        status: cancelled ? 'stopping' : 'running', stage: 'sql_generation', completed_tasks: 0,
        total_tasks: null, stop_reason: cancelled ? 'user_cancelled' : null, draft_generation: 0,
      } };
    return route.fulfill({ status: 200, contentType: 'text/event-stream',
      body: `id: 0\nevent: snapshot\ndata: ${JSON.stringify(event)}\n\n` });
  });
  await page.route('**/api/v1/executions/*/cancel', async route => {
    cancelled = true;
    cancelBody = route.request().postDataJSON();
    cancelMarker = route.request().headers()['x-chatbi-request'] ?? '';
    return route.fulfill({ status: 202, json: { execution: { id: executionId, status: 'stopping',
      stop_reason: 'user_cancelled' } } });
  });

  await login(page);
  await send(page, question);
  await expect(page.getByRole('status')).toContainText('生成查询');
  await page.getByRole('button', { name: '取消执行', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('正在取消执行…');
  await expect(page.getByRole('button', { name: '取消执行', exact: true })).toHaveCount(0);
  expect(cancelBody).toEqual({});
  expect(cancelMarker).toBe('browser');
  expect(eventReads).toBeGreaterThan(0);
});

for (const { reason, message } of [
  { reason: 'deadline_exceeded', message: '执行超时，正在停止…' },
  { reason: 'authorization_revoked', message: '执行权限已变化，正在停止…' },
]) {
  test(`网页显示${message}状态`, async ({ page }) => {
    const historyId = '00000000-0000-4000-8000-000000000031';
    const turnId = '00000000-0000-4000-8000-000000000032';
    const executionId = '00000000-0000-4000-8000-000000000033';
    const operationId = '00000000-0000-4000-8000-000000000034';
    const question = '服务端停止中的查询';
    const history = { id: historyId, kind: 'query', title: question, first_question: question,
      created_at: '2026-10-05T00:00:00Z', updated_at: '2026-10-05T00:00:00Z', context_revision: 0,
      record_revision: 1, active: true, can_continue: false, can_resume: false,
      last_success_turn_id: null, active_turn_id: turnId, analysis_run_id: null };
    const turn = { id: turnId, history_id: historyId, ordinal: 1, question, status: 'accepted',
      public_error: null, execution_id: executionId };
    await page.route('**/api/v1/histories**', async route => {
      const url = new URL(route.request().url()); const path = url.pathname; const method = route.request().method();
      if (path === '/api/v1/histories' && method === 'POST') {
        return route.fulfill({ status: 201, json: { ...history, active: false, active_turn_id: null } });
      }
      if (path === `/api/v1/histories/${historyId}/executions` && method === 'POST') {
        return route.fulfill({ status: 202, json: { execution: { id: executionId, history_id: historyId,
          turn_id: turnId, operation_id: operationId, mode: 'query', operation_kind: 'query',
          status: 'accepted', stop_reason: null }, history, turn } });
      }
      return route.continue();
    });
    await page.route('**/api/v1/executions/*/events', async route => {
      const event = { version: 1, execution_id: executionId, history_id: historyId, turn_id: turnId,
        sequence: 0, draft_generation: 0, type: 'snapshot', payload: {
          status: 'stopping', stage: 'sql_generation', completed_tasks: 0,
          total_tasks: null, stop_reason: reason, draft_generation: 0,
        } };
      return route.fulfill({ status: 200, contentType: 'text/event-stream',
        body: `id: 0\nevent: snapshot\ndata: ${JSON.stringify(event)}\n\n` });
    });

    await login(page);
    await send(page, question);
    await expect(page.getByRole('status')).toHaveText(message);
    await expect(page.getByRole('button', { name: '取消执行', exact: true })).toHaveCount(0);
  });
}

test('问数取消终态保留上一成功上下文并允许用户新建下一轮', async ({ page }) => {
  const historyId = '00000000-0000-4000-8000-000000000041';
  const previousTurnId = '00000000-0000-4000-8000-000000000042';
  const cancelledTurnId = '00000000-0000-4000-8000-000000000043';
  const nextTurnId = '00000000-0000-4000-8000-000000000044';
  const cancelledExecutionId = '00000000-0000-4000-8000-000000000045';
  const nextExecutionId = '00000000-0000-4000-8000-000000000046';
  const history = { id: historyId, kind: 'query', title: '销售额', first_question: '销售额',
    created_at: '2026-10-05T00:00:00Z', updated_at: '2026-10-05T00:00:00Z', context_revision: 1,
    record_revision: 2, active: false, can_continue: true, can_resume: false,
    last_success_turn_id: previousTurnId, active_turn_id: null, analysis_run_id: null };
  const previousTurn = { id: previousTurnId, history_id: historyId, ordinal: 1, question: '销售额', status: 'succeeded',
    public_error: null, snapshot: { request_id: 'saved-r', sql: 'SELECT 12', columns: ['销售额'], rows: [['12.50']],
      row_count: 1, truncated: false } };
  const cancelledTurn = { id: cancelledTurnId, history_id: historyId, ordinal: 2, question: '取消中的追问',
    status: 'failed', public_error: { error_code: 'EXECUTION_CANCELLED', error_message: '执行已取消' },
    execution_id: cancelledExecutionId };
  let currentHeader = history;
  let cancellationConfirmed = false;
  const submissions: Array<Record<string, unknown>> = [];

  await page.route('**/api/v1/histories**', async route => {
    const url = new URL(route.request().url()); const path = url.pathname; const method = route.request().method();
    if (path === `/api/v1/histories/${historyId}/executions` && method === 'POST') {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      submissions.push(body);
      if (submissions.length === 1) {
        currentHeader = { ...history, active: true, active_turn_id: cancelledTurnId, record_revision: 3 };
        return route.fulfill({ status: 202, json: { execution: { id: cancelledExecutionId,
          history_id: historyId, turn_id: cancelledTurnId, operation_id: body.operation_id,
          mode: 'query', operation_kind: 'query', status: 'accepted', stop_reason: null },
          history: currentHeader, turn: { ...cancelledTurn, status: 'accepted', public_error: null } } });
      }
      const nextTurn = { id: nextTurnId, history_id: historyId, ordinal: 3, question: body.question,
        status: 'accepted', public_error: null, execution_id: nextExecutionId };
      currentHeader = { ...history, active: true, active_turn_id: nextTurnId, record_revision: 5 };
      return route.fulfill({ status: 202, json: { execution: { id: nextExecutionId,
        history_id: historyId, turn_id: nextTurnId, operation_id: body.operation_id,
        mode: 'query', operation_kind: 'query', status: 'accepted', stop_reason: null },
        history: currentHeader, turn: nextTurn } });
    }
    if (path === `/api/v1/histories/${historyId}` && method === 'GET') {
      return route.fulfill({ json: currentHeader });
    }
    if (path === `/api/v1/histories/${historyId}/turns` && method === 'GET') {
      const turns = cancellationConfirmed ? [previousTurn, cancelledTurn] : [previousTurn];
      return route.fulfill({ json: { items: turns.map(turn => ({ ...turn, snapshot: undefined })), next_cursor: null } });
    }
    if (path === `/api/v1/histories/${historyId}/turns/${previousTurnId}` && method === 'GET') {
      return route.fulfill({ json: previousTurn });
    }
    if (path === `/api/v1/histories/${historyId}/turns/${cancelledTurnId}` && method === 'GET') {
      return route.fulfill({ json: cancelledTurn });
    }
    if (path === '/api/v1/histories' && method === 'GET') {
      return route.fulfill({ json: { items: [currentHeader], next_cursor: null } });
    }
    return route.continue();
  });
  await page.route('**/api/v1/executions/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/events')) {
      const executionId = path.includes(cancelledExecutionId) ? cancelledExecutionId : nextExecutionId;
      const turnId = executionId === cancelledExecutionId ? cancelledTurnId : nextTurnId;
      const frame = (sequence: number, type: string, payload: Record<string, unknown>) => {
        const event = { version: 1, execution_id: executionId, history_id: historyId, turn_id: turnId,
          sequence, draft_generation: 0, type, payload };
        return `id: ${sequence}\nevent: ${type}\ndata: ${JSON.stringify(event)}\n\n`;
      };
      const body = executionId === cancelledExecutionId && cancellationConfirmed
        ? frame(1, 'terminal', { status: 'cancelled', public_error: cancelledTurn.public_error })
        : frame(0, 'snapshot', { status: 'running', stage: 'sql_generation', completed_tasks: 0,
          total_tasks: null, stop_reason: null, draft_generation: 0 });
      return route.fulfill({ status: 200, contentType: 'text/event-stream', body });
    }
    if (path.endsWith('/cancel') && route.request().method() === 'POST') {
      cancellationConfirmed = true;
      currentHeader = { ...history, active: false, active_turn_id: null, record_revision: 4 };
      return route.fulfill({ status: 200, json: { execution: { id: cancelledExecutionId, status: 'cancelled',
        stop_reason: 'user_cancelled' }, history: currentHeader, turn: cancelledTurn } });
    }
    if (path === `/api/v1/executions/${cancelledExecutionId}` && route.request().method() === 'GET') {
      return route.fulfill({ json: { execution: { id: cancelledExecutionId, status: 'cancelled',
        stop_reason: 'user_cancelled' }, history: currentHeader, turn: cancelledTurn } });
    }
    return route.continue();
  });

  await login(page);
  await page.goto(`/#history=${historyId}`);
  await expect(page.getByText('12.50', { exact: true })).toBeVisible();
  await send(page, '取消中的追问');
  await expect(page.getByRole('status')).toContainText('生成查询');
  await page.getByRole('button', { name: '取消执行', exact: true }).click();
  await expect(page.getByText('执行已取消', { exact: true })).toBeVisible();
  await send(page, '取消后新建追问');
  await expect.poll(() => submissions.length).toBe(2);
  expect(submissions[0].expected_context_revision).toBe(1);
  expect(submissions[1]).toMatchObject({ question: '取消后新建追问', expected_context_revision: 1 });
});

test('reducer忽略重复帧、检测序号缺口与阶段回退，并接受低序号持久终态', () => {
  const identity: ExecutionIdentity = { executionId: 'exec', historyId: 'history', turnId: 'turn' };
  const event = (sequence: number, type: string, payload: Record<string, unknown>) => decodeExecutionEvent({
    version: 1, execution_id: identity.executionId, history_id: identity.historyId, turn_id: identity.turnId,
    sequence, draft_generation: 0, type, payload,
  }, identity);
  const initial = event(0, 'snapshot', { status: 'running', stage: 'retrieval', completed_tasks: 1, total_tasks: 3,
    stop_reason: null, draft_generation: 0 });
  const initialState = reduceExecutionEvent(null, initial).state;
  const advanced = event(1, 'progress', { stage: 'query_execution', completed_tasks: 2, total_tasks: 3 });
  const advancedState = reduceExecutionEvent(initialState, advanced).state;
  const stopping = event(2, 'progress', { status: 'stopping', stop_reason: 'user_cancelled' });
  expect(reduceExecutionEvent(advancedState, stopping).state).toMatchObject({
    status: 'stopping', stopReason: 'user_cancelled',
  });
  expect(reduceExecutionEvent(advancedState, advanced).state).toEqual(advancedState);
  expect(reduceExecutionEvent(advancedState, event(3, 'progress', { stage: 'result_saving' })).resnapshot).toBe(true);
  expect(reduceExecutionEvent(advancedState, event(2, 'progress', { completed_tasks: 1, total_tasks: null })).resnapshot).toBe(true);
  expect(reduceExecutionEvent(advancedState, event(2, 'snapshot', { status: 'running', stage: 'retrieval', completed_tasks: 1,
    total_tasks: 3, stop_reason: null, draft_generation: 0 })).resnapshot).toBe(true);
  expect(() => event(2, 'progress', { status: 'succeeded' })).toThrow('执行状态无效');
  const persistedTerminal = event(0, 'snapshot', { status: 'succeeded', stage: null, completed_tasks: 0, total_tasks: null,
    stop_reason: null, draft_generation: 0 });
  expect(reduceExecutionEvent(advancedState, persistedTerminal).state).toMatchObject({
    status: 'succeeded', stage: 'query_execution', completedTasks: 2, sequence: 1,
  });
});

test('SSE单帧默认接收上限为6MiB', () => {
  const parser = new SSEParser();
  const limit = 6 * 1024 * 1024;
  parser.feed(new Uint8Array(limit));
  expect(() => parser.feed(new Uint8Array(1))).toThrow('执行事件超过网页接收上限');
});
