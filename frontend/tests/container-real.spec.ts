import { test, expect, type Page } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import { login, send, isFinalExecutionResponse } from './helpers';
import { querySnapshot } from '../src/results';
import { analysisResult } from '../src/Analysis';
import { buildChartPlans } from '../src/chartPlan';

const executionStages = new Set([
  'query_understanding', 'retrieval', 'sql_generation', 'sql_validation', 'query_execution', 'result_saving',
  'analysis_understanding', 'analysis_plan_validation', 'analysis_query_tasks', 'analysis_attribution', 'analysis_report_generation',
]);

type ExecutionStreamEvidence = {
  execution_id: string;
  http_statuses: number[];
  event_types: string[];
  stages: string[];
  terminal_statuses: string[];
  event_count: number;
  text_delta_count: number;
  first_text_delta_sequence: number | null;
  succeeded_sequence: number | null;
};

declare global {
  interface Window {
    __chatbiExecutionEvidence?: Record<string, ExecutionStreamEvidence>;
    __chatbiCaptureExecutionStreams?: boolean;
  }
}

async function captureExecutionStreams(page: Page) {
  const connections = new Map<string, number>();
  const submissions: string[] = [];
  await page.addInitScript((allowedStages: string[]) => {
    const target = window as Window & { __chatbiExecutionEvidence?: Record<string, ExecutionStreamEvidence> };
    const allowed = new Set(allowedStages);
    const terminal = new Set(['succeeded', 'failed', 'cancelled', 'timed_out', 'unconfirmed']);
    const originalFetch = window.fetch.bind(window);
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const response = await originalFetch(input, init);
      const requestUrl = input instanceof Request ? input.url : String(input);
      const match = new URL(requestUrl, location.href).pathname.match(/^\/api\/v1\/executions\/([0-9a-f-]{36})\/events$/);
      if (!match || response.status >= 400 || !response.body || !target.__chatbiCaptureExecutionStreams) return response;
      const executionId = match[1];
      const evidence = target.__chatbiExecutionEvidence ??= {};
      const summary = evidence[executionId] ??= {
        execution_id: executionId, http_statuses: [], event_types: [], stages: [], terminal_statuses: [], event_count: 0,
        text_delta_count: 0, first_text_delta_sequence: null, succeeded_sequence: null,
      };
      if (!summary.http_statuses.includes(response.status)) summary.http_statuses.push(response.status);
      const reader = response.clone().body?.getReader();
      if (reader) void (async () => {
        const decoder = new TextDecoder();
        let buffered = '';
        const consume = (frame: string) => {
          let eventType = 'message';
          const data: string[] = [];
          for (const line of frame.split(/\r?\n/)) {
            if (line.startsWith('event:')) eventType = line.slice(6).trim();
            else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
          }
          if (!data.length) return;
          let event: Record<string, unknown>;
          try { event = JSON.parse(data.join('\n')) as Record<string, unknown>; }
          catch { return; }
          if (event.execution_id !== executionId) return;
          summary.event_count += 1;
          if (!summary.event_types.includes(eventType)) summary.event_types.push(eventType);
          const payload = event.payload && typeof event.payload === 'object' ? event.payload as Record<string, unknown> : {};
          if (typeof payload.stage === 'string' && allowed.has(payload.stage) && !summary.stages.includes(payload.stage)) {
            summary.stages.push(payload.stage);
          }
          if (typeof payload.status === 'string' && terminal.has(payload.status) && !summary.terminal_statuses.includes(payload.status)) {
            summary.terminal_statuses.push(payload.status);
          }
          if (eventType === 'text_delta' && typeof payload.text === 'string' && payload.text.length > 0) {
            summary.text_delta_count += 1;
            if (summary.first_text_delta_sequence === null && Number.isSafeInteger(event.sequence)) {
              summary.first_text_delta_sequence = Number(event.sequence);
            }
          }
          if (eventType === 'terminal' && payload.status === 'succeeded' && Number.isSafeInteger(event.sequence)) {
            summary.succeeded_sequence = Number(event.sequence);
          }
        };
        try {
          while (true) {
            const { done, value } = await reader.read();
            buffered += decoder.decode(value, { stream: !done });
            const frames = buffered.split(/\r?\n\r?\n/);
            buffered = frames.pop() ?? '';
            frames.forEach(consume);
            if (done) {
              if (buffered.trim()) consume(buffered);
              return;
            }
          }
        } finally { reader.releaseLock(); }
      })().catch(() => undefined);
      return response;
    };
  }, [...executionStages]);
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    const eventMatch = path.match(/^\/api\/v1\/executions\/([0-9a-f-]{36})\/events$/);
    if (request.method() === 'GET' && eventMatch) {
      const executionId = eventMatch[1];
      connections.set(executionId, (connections.get(executionId) ?? 0) + 1);
    }
    if (request.method() === 'POST' && /^\/api\/v1\/histories\/[0-9a-f-]{36}\/executions$/.test(path)) submissions.push(path);
  });
  return {
    submissions,
    connectionCount(executionId: string): number { return connections.get(executionId) ?? 0; },
    async forExecution(executionId: string): Promise<ExecutionStreamEvidence> {
      await expect.poll(() => page.evaluate(id =>
        window.__chatbiExecutionEvidence?.[id]?.terminal_statuses.includes('succeeded') ?? false, executionId),
      { timeout: 30000 }).toBe(true);
      return await page.evaluate(id => window.__chatbiExecutionEvidence?.[id]!, executionId);
    },
  };
}

function isExecutionSubmission(response: { url(): string; request(): { method(): string } }): boolean {
  return response.request().method() === 'POST'
    && /^\/api\/v1\/histories\/[0-9a-f-]{36}\/executions$/.test(new URL(response.url()).pathname);
}

async function executionView(page: Page, executionId: string, userId: number): Promise<{
  execution: { status: string };
  history: { last_success_turn_id: string | null };
}> {
  const origin = new URL(page.url()).origin;
  const response = await page.request.get(`${origin}/api/v1/executions/${executionId}`, {
    headers: { 'X-ChatBI-User-ID': String(userId) },
  });
  expect(response.ok()).toBe(true);
  const body = await response.json() as Record<string, unknown>;
  const execution = body.execution as Record<string, unknown>;
  const history = body.history as Record<string, unknown>;
  return {
    execution: { status: String(execution.status) },
    history: { last_success_turn_id: typeof history.last_success_turn_id === 'string' ? history.last_success_turn_id : null },
  };
}

test('源码挂载实际触发 Python 重载与 Vite 热更新', async ({ page }) => {
  test.skip(process.env.CHATBI_CONTAINER_RESTART_PHASE === '1');
  const backend = '/workspace/backend-src/query_api/app.py';
  const css = '/workspace/frontend/src/style.css';
  const originalBackend = readFileSync(backend, 'utf8');
  const originalCss = readFileSync(css, 'utf8');
  const marker = 'return {"status": "ok"}';
  expect(originalBackend.split(marker).length).toBe(2);
  const changedBackend = originalBackend.replace(marker, 'return {"status": "hot-reload-check"}');
  const changedCss = `${originalCss}\nbody { --chatbi-hot-check: 1; }\n`;
  await page.goto('/');
  try {
    writeFileSync(backend, changedBackend);
    await expect.poll(async () => {
      try { return (await (await page.request.get('/health')).json()).status; } catch { return 'restarting'; }
    }, { timeout: 60000 }).toBe('hot-reload-check');
    writeFileSync(css, changedCss);
    await expect.poll(() => page.evaluate(() => getComputedStyle(document.body).getPropertyValue('--chatbi-hot-check').trim()),
      { timeout: 30000 }).toBe('1');
    writeFileSync('/reports/hot-reload.json', JSON.stringify({
      commit: process.env.CHATBI_CONTAINER_COMMIT, experiment_dirty: true,
      python_reload: true, vite_hmr: true,
    }));
  } finally {
    let concurrentChange = false;
    if (readFileSync(backend, 'utf8') === changedBackend) writeFileSync(backend, originalBackend);
    else concurrentChange = true;
    const currentCss = readFileSync(css, 'utf8');
    if (currentCss === changedCss) writeFileSync(css, originalCss);
    else if (currentCss !== originalCss) concurrentChange = true;
    if (concurrentChange) throw new Error('源码被并发修改，已恢复可安全恢复的文件并保留现场');
  }
  await expect.poll(async () => {
    try { return (await (await page.request.get('/health')).json()).status; } catch { return 'restarting'; }
  }, { timeout: 60000 }).toBe('ok');
});

test('实际 Compose 网页登录 → 真实问数 → 同一对话追问', async ({ page, browser }) => {
  test.skip(process.env.CHATBI_CONTAINER_RESTART_PHASE === '1');
  const reference = JSON.parse(process.env.CHATBI_CONTAINER_REFERENCE!);
  const evidence: Record<string, unknown> = {
    commit: process.env.CHATBI_CONTAINER_COMMIT, git_dirty: process.env.CHATBI_CONTAINER_GIT_DIRTY === 'true',
    username: process.env.CHATBI_REAL_E2E_USERNAME, reference,
    at: new Date().toISOString(), browser: browser.version(), target: 'compose-vite-api',
  };
  const streams = await captureExecutionStreams(page);
  const account = JSON.parse(readFileSync('/reports/account.json', 'utf8')) as { id: number };
  try {
    await login(page, process.env.CHATBI_REAL_E2E_USERNAME!, process.env.CHATBI_REAL_E2E_PASSWORD!);
    await page.evaluate(() => { window.__chatbiCaptureExecutionStreams = true; });
    const firstResponse = page.waitForResponse(isFinalExecutionResponse, { timeout: 240000 });
    await send(page, '2025年2月已完成订单的人民币净销售额是多少？');
    const firstHttp = await firstResponse;
    const firstPayload = await firstHttp.json();
    evidence.first_http_status = firstHttp.status();
    evidence.first_error_code = firstPayload.error_code;
    const first = querySnapshot(firstPayload.turn.snapshot);
    expect(first.rows.length).toBe(1);
    expect(Number(first.rows[0][0])).toBe(Number(reference.net_sales['2']));
    evidence.step = 'query-sse-capture';
    const firstStream = await streams.forExecution(firstPayload.execution.id);
    evidence.step = 'query-stage-evidence';
    evidence.query_execution_stream = firstStream;
    expect(firstStream.stages).toContain('result_saving');
    expect(firstStream.stages.some(stage => ['sql_validation', 'query_execution'].includes(stage))).toBe(true);
    expect(firstStream.terminal_statuses).toContain('succeeded');
    await expect(page.getByRole('table')).toBeVisible();
    const secondResponse = page.waitForResponse(isFinalExecutionResponse, { timeout: 240000 });
    await send(page, '改成2025年3月');
    const secondHttp = await secondResponse;
    const secondPayload = await secondHttp.json();
    evidence.followup_http_status = secondHttp.status();
    evidence.followup_error_code = secondPayload.error_code;
    if (!secondPayload.turn?.snapshot) throw new Error('follow-up did not commit a successful snapshot');
    const second = querySnapshot(secondPayload.turn.snapshot);
    expect(secondPayload.history.id).toBe(firstPayload.history.id);
    expect(Number(second.rows[0][0])).toBe(Number(reference.net_sales['3']));
    evidence.query = { value: first.rows[0][0], history_id: firstPayload.history.id };
    evidence.followup = { value: second.rows[0][0], history_id: secondPayload.history.id };
    expect(first.result_metadata?.columns[0].semantic_name).toBe('人民币净销售额');
    expect(first.result_metadata?.columns[0].unit?.key).toBe('CNY');
    expect(first.result_metadata?.scope.time?.start).toBe('2025-02-01');
    expect(second.result_metadata?.scope.time?.start).toBe('2025-03-01');
    await page.getByRole('button', { name: '新建问数对话' }).click();
    const trendResponse = page.waitForResponse(isFinalExecutionResponse, { timeout: 240000 });
    await send(page, '按月份列出2025年已完成订单的人民币净销售额、人民币毛利和毛利率。');
    evidence.step = 'monthly-query';
    const trendHttp = await trendResponse;
    const trendPayload = await trendHttp.json();
    evidence.monthly_http_status = trendHttp.status();
    evidence.monthly_error_code = trendPayload.error_code ?? trendPayload.turn?.error_code;
    if (!trendPayload.turn?.snapshot) throw new Error('monthly query did not commit a successful snapshot');
    const trend = querySnapshot(trendPayload.turn.snapshot);
    const trendMetadata = trend.result_metadata!;
    expect(trendMetadata.scope.grouping).toHaveLength(1);
    expect(trendMetadata.time_axis?.granularity).toBe('month');
    const metricNames = ['人民币净销售额', '人民币毛利', '毛利率'];
    expect(trend.rows.length).toBe(Object.keys(reference.monthly).length);
    trend.rows.forEach((row, index) => {
      const expected = reference.monthly[trendMetadata.time_axis!.keys[index]];
      expect(expected).toBeTruthy();
      metricNames.forEach((name, metricIndex) => {
        const column = trendMetadata.columns.find(c => c.semantic_name === name && c.certified)!;
        expect(column).toBeTruthy();
        expect(Number(row[column.index])).toBeCloseTo(Number(expected[metricIndex]), 8);
      });
    });
    const trendPlans = buildChartPlans(trend);
    expect(trendPlans.plans).toHaveLength(2);
    expect(trendPlans.plans.find(p => p.id === 'CNY')?.series).toHaveLength(2);
    await expect(page.locator('.chart-canvas svg')).toHaveCount(2);
    await expect(page.getByRole('table')).toBeVisible();
    await page.getByLabel('图表类型').first().selectOption('bar');
    await expect(page.locator('[data-chart-kind="bar"] svg')).toHaveCount(1);
    evidence.monthly_mixed_units = { rows: trend.rows.length, reference_matches: true, money_series: 2, chart_units: trendPlans.plans.map(p => p.id), metadata_status: trendMetadata.status };
    await page.getByRole('button', { name: '新建问数对话' }).click();
    const categoryResponse = page.waitForResponse(isFinalExecutionResponse, { timeout: 240000 });
    await send(page, '按产品线列出2025年已完成订单的人民币净销售额和人民币销售成本。');
    const categoryPayload = await (await categoryResponse).json();
    const category = querySnapshot(categoryPayload.turn.snapshot);
    const categoryMeta = category.result_metadata!;
    const dimension = categoryMeta.columns.find(c => c.semantic_name === '产品线' && c.certified)!;
    expect(dimension).toBeTruthy();
    expect(category.rows.length).toBe(Object.keys(reference.categories).length);
    category.rows.forEach(row => {
      const expected = reference.categories[String(row[dimension.index])];
      expect(expected).toBeTruthy();
      ['人民币净销售额', '人民币销售成本'].forEach((name, metricIndex) => {
        const column = categoryMeta.columns.find(c => c.semantic_name === name && c.certified)!;
        expect(column).toBeTruthy();
        expect(Number(row[column.index])).toBeCloseTo(Number(expected[metricIndex]), 8);
      });
    });
    expect(buildChartPlans(category).plans[0].series).toHaveLength(2);
    await expect(page.locator('.chart-canvas svg')).toHaveCount(1);
    evidence.category_same_unit = { rows: category.rows.length, reference_matches: true, series: 2, metadata_status: categoryMeta.status };
    evidence.step = 'analysis-request';
    await page.getByRole('button', { name: '经营分析', exact: true }).click();
    const analysisResponse = page.waitForResponse(isFinalExecutionResponse, { timeout: 600000 });
    await send(page, '分析2025年3月相比2025年2月的人民币毛利变化及产品因素贡献。');
    const analysisHttp = await analysisResponse;
    evidence.analysis_http_status = analysisHttp.status();
    evidence.step = 'analysis-parse';
    const analysisPayload = await analysisHttp.json();
    const analysisStream = await streams.forExecution(analysisPayload.execution.id);
    evidence.step = 'analysis-stage-evidence';
    evidence.analysis_execution_stream = analysisStream;
    expect(analysisStream.stages).toContain('analysis_report_generation');
    expect(analysisStream.stages).toContain('result_saving');
    expect(analysisStream.stages).toContain('analysis_query_tasks');
    expect(analysisStream.terminal_statuses).toContain('succeeded');
    expect(analysisStream.text_delta_count).toBeGreaterThan(0);
    expect(analysisStream.first_text_delta_sequence).not.toBeNull();
    expect(analysisStream.succeeded_sequence).not.toBeNull();
    expect(analysisStream.first_text_delta_sequence!).toBeLessThan(analysisStream.succeeded_sequence!);
    const analysis = analysisResult(analysisPayload.turn.snapshot, analysisPayload.history.analysis_run_id);
    evidence.step = 'analysis-reference';
    const { reconciliation_passed: _reconciled, ...expectedAttribution } = reference.attribution;
    expect(analysis.report.attribution).toEqual(expect.objectContaining(expectedAttribution));
    expect(analysis.task_results).toHaveLength(4);
    expect(analysis.task_results.every(t => t.status === 'completed' && !t.truncated)).toBe(true);
    evidence.step = 'analysis-render';
    await expect(page.locator('.attribution .chart-canvas svg')).toHaveCount(2);
    await expect(page.locator('.attribution table')).toBeVisible();
    await page.getByText('查看查询任务证据').click();
    await expect(page.getByText('查看查询任务证据').locator('..').getByRole('table')).toHaveCount(4);
    evidence.analysis = { reference_matches: true, direction: analysis.report.attribution!.direction, tasks_completed: 4, task_metadata: analysis.task_results.map(t => t.result_metadata?.status ?? 'absent'), product_factor_charts: true };
    evidence.step = 'r3-history';
    const analysisUrl = page.url();
    await page.reload(); await expect(page.locator('.analysis-report h2')).toBeVisible();
    await page.getByRole('button', { name: '另存成果', exact: true }).click();
    await page.getByLabel('成果名称').fill('R3固定分析报告');
    await page.getByRole('button', { name: '保存名称', exact: true }).click();
    await expect(page.getByText('已保存。', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: '问数', exact: true }).click();
    evidence.step = 'history-search-query';
    await page.getByLabel('记录类型').selectOption('query');
    await page.getByLabel('搜索名称').fill('按产品线列出2025年已完成订单');
    await page.getByRole('button', { name: '搜索', exact: true }).click();
    await page.getByRole('button', { name: /问数 · 按产品线列出2025年已完成订单/ }).click();
    await expect(page.getByRole('table')).toBeVisible();
    await page.getByLabel('搜索名称').fill('');
    await page.getByRole('button', { name: '搜索', exact: true }).click();
    evidence.step = 'save-query-result';
    await page.getByRole('button', { name: '另存成果', exact: true }).click();
    await page.getByLabel('成果名称').fill('R3固定分类成果');
    await page.getByRole('button', { name: '保存名称', exact: true }).click();
    await expect(page.getByText('已保存。', { exact: true })).toBeVisible();
    page.on('dialog', dialog => dialog.accept());
    evidence.step = 'delete-source-history';
    await page.getByRole('button', { name: '删除历史', exact: true }).click();
    await expect(page.getByRole('table')).toHaveCount(0);
    await page.getByRole('button', { name: '已保存成果', exact: true }).click();
    evidence.step = 'open-saved-copy';
    await page.getByRole('button', { name: '问数 · R3固定分类成果', exact: true }).click();
    await expect(page.getByRole('table')).toBeVisible();
    const savedUrl = page.url();
    await page.getByRole('button', { name: '新建问数对话', exact: true }).click();
    evidence.step = 'top-n-query';
    const rankedResponse = page.waitForResponse(isFinalExecutionResponse, { timeout: 240000 });
    await send(page, '2025年3月按人民币净销售额从高到低列出前3个产品。');
    const rankedPayload = await (await rankedResponse).json(); const ranked = querySnapshot(rankedPayload.turn.snapshot);
    expect(ranked.rows.map(row => [String(row[0]), Number(row[1])])).toEqual(reference.top_products.map((row: unknown[]) => [String(row[0]), Number(row[1])]));
    evidence.restart_inputs = { ranked_history_id: rankedPayload.history.id, analysis_history_id: analysisPayload.history.id, analysis_run_id: analysisPayload.history.analysis_run_id, saved_url: savedUrl, analysis_url: analysisUrl };
    evidence.r3_before_restart = { saved_independent: true, refresh_analysis: true, top_n_reference: true };

    evidence.step = 'multi-page-disconnect-and-cancel';
    await page.evaluate(() => { window.__chatbiCaptureExecutionStreams = false; });
    const submissionsBeforeRecovery = streams.submissions.length;
    const cancelableResponse = page.waitForResponse(isExecutionSubmission, { timeout: 30000 });
    await send(page, '只看前2个产品');
    const cancelableAcceptance = await cancelableResponse;
    const cancelableBody = await cancelableAcceptance.json();
    const cancelableExecutionId = cancelableBody.execution.id as string;
    const cancelableHistoryId = cancelableBody.history.id as string;
    expect(cancelableHistoryId).toBe(rankedPayload.history.id);

    const secondPage = await page.context().newPage();
    const secondStreams = await captureExecutionStreams(secondPage);
    const isEventResponse = (response: { url(): string; request(): { method(): string } }) =>
      response.request().method() === 'GET'
        && new URL(response.url()).pathname === `/api/v1/executions/${cancelableExecutionId}/events`;
    const secondPageAttached = secondPage.waitForResponse(isEventResponse, { timeout: 30000 });
    await secondPage.goto('/#history=' + cancelableHistoryId);
    await expect(secondPage.getByRole('button', { name: '退出登录' })).toBeVisible();
    await secondPageAttached;
    const attachedExecution = await executionView(secondPage, cancelableExecutionId, account.id);
    const canCancelAtSecondPage = ['accepted', 'running'].includes(attachedExecution.execution.status);

    await expect.poll(() => streams.connectionCount(cancelableExecutionId), { timeout: 30000 }).toBeGreaterThan(0);
    const firstPageReattach = page.waitForResponse(isEventResponse, { timeout: 30000 });
    await page.reload();
    await firstPageReattach;
    const executionPostsAfterReattach = streams.submissions.length + secondStreams.submissions.length;
    expect(executionPostsAfterReattach - submissionsBeforeRecovery).toBe(1);

    let cancelObservation: Record<string, unknown> = { attempted: false, status_before: attachedExecution.execution.status };
    const cancelButton = secondPage.getByRole('button', { name: '取消执行', exact: true });
    if (canCancelAtSecondPage) {
      await expect(secondPage.getByText('当前账号已有执行，完成后可继续提交', { exact: true })).toBeVisible();
      await expect(cancelButton).toBeVisible({ timeout: 5000 }).catch(() => undefined);
      if (await cancelButton.isVisible()) {
        const cancelResponse = secondPage.waitForResponse(response => response.request().method() === 'POST'
          && new URL(response.url()).pathname === `/api/v1/executions/${cancelableExecutionId}/cancel`, { timeout: 30000 });
        await cancelButton.click();
        const response = await cancelResponse;
        const body = await response.json();
        cancelObservation = {
          attempted: true, http_status: response.status(), status_before: attachedExecution.execution.status,
          status_after_request: body.execution.status,
        };
      } else {
        const statusAtCancel = await executionView(secondPage, cancelableExecutionId, account.id);
        if (['accepted', 'running'].includes(statusAtCancel.execution.status)) {
          throw new Error('执行仍在运行时第二个标签页没有显示取消入口');
        }
        cancelObservation = {
          attempted: false, status_before: attachedExecution.execution.status,
          status_at_cancel: statusAtCancel.execution.status, completion_race: true,
        };
      }
    }
    await expect.poll(async () => (await executionView(secondPage, cancelableExecutionId, account.id)).execution.status,
      { timeout: 180000, intervals: [250, 500, 1000, 2000, 5000] }).toMatch(/^(succeeded|failed|cancelled|timed_out|unconfirmed)$/);
    const cancelableFinal = await executionView(secondPage, cancelableExecutionId, account.id);
    cancelObservation.status_final = cancelableFinal.execution.status;
    cancelObservation.last_success_turn_preserved = cancelableFinal.history.last_success_turn_id === cancelableBody.history.last_success_turn_id;
    if (['failed', 'cancelled', 'timed_out', 'unconfirmed'].includes(cancelableFinal.execution.status)) {
      expect(cancelObservation.last_success_turn_preserved).toBe(true);
    }
    evidence.multi_page_recovery = {
      execution_id: cancelableExecutionId, same_history_attached: true, browser_reload_reconnected: true,
      submissions_for_operation: executionPostsAfterReattach - submissionsBeforeRecovery,
      first_page_streams: streams.connectionCount(cancelableExecutionId),
      second_page_streams: secondStreams.connectionCount(cancelableExecutionId), cancel: cancelObservation,
    };
    await secondPage.close();

    evidence.step = 'post-cancel-new-operation';
    const nextQuery = page.waitForResponse(isFinalExecutionResponse, { timeout: 240000 });
    await send(page, '只看前2个产品');
    const nextPayload = await (await nextQuery).json();
    expect(nextPayload.history.id).toBe(rankedPayload.history.id);
    const nextResult = querySnapshot(nextPayload.turn.snapshot);
    expect(nextResult.rows.map(row => [String(row[0]), Number(row[1])])).toEqual(
      reference.top_products.slice(0, 2).map((row: unknown[]) => [String(row[0]), Number(row[1])]),
    );
    evidence.after_cancel_or_completion = { terminal_status: cancelableFinal.execution.status, new_operation_reference_matches: true };

    evidence.step = 'restart-unconfirmed-setup';
    const interruptedResponse = page.waitForResponse(isExecutionSubmission, { timeout: 30000 });
    await send(page, '2025年3月人民币净销售额最高的产品是什么？');
    const interruptedAcceptance = await interruptedResponse;
    expect(interruptedAcceptance.status()).toBe(202);
    const interruptedBody = await interruptedAcceptance.json();
    expect(interruptedBody.history.id).toBe(rankedPayload.history.id);
    evidence.restart_inputs = {
      ...(evidence.restart_inputs as Record<string, unknown>),
      interrupted_execution: {
        history_id: interruptedBody.history.id, execution_id: interruptedBody.execution.id, turn_id: interruptedBody.turn.id,
        prior_success_turn_id: interruptedBody.history.last_success_turn_id,
      },
    };
    evidence.step = 'complete';
    evidence.status = 'passed';
  } catch (error) {
    evidence.status = 'failed'; evidence.error_type = (error as Error).name;
    evidence.error_locations = (error as Error).stack?.match(/container-real\.spec\.ts:\d+:\d+/g) ?? [];
    throw new Error('真实容器业务验收失败，见私有报告的步骤与安全定位。');
  } finally {
    writeFileSync('/reports/browser.json', JSON.stringify(evidence, null, 2));
  }
});


test('停止重启后读取长期快照、重登录、续聊与显式重查', async ({ page }) => {
  test.skip(process.env.CHATBI_CONTAINER_RESTART_PHASE !== '1');
  const evidence = JSON.parse(readFileSync('/reports/browser.json', 'utf8'));
  const input = evidence.restart_inputs; const reference = evidence.reference;
  try {
    await login(page, process.env.CHATBI_REAL_E2E_USERNAME!, process.env.CHATBI_REAL_E2E_PASSWORD!);
    await expect(page.getByRole('table')).toHaveCount(0);
    await page.goto('/#history=' + input.ranked_history_id);
    await expect(page.getByRole('table')).toBeVisible();
    if (input.interrupted_execution) {
      await expect(page.getByText('结果未确认；请刷新后明确选择下一步。', { exact: true })).toBeVisible();
      expect(evidence.execution_recovery).toEqual(expect.objectContaining({
        execution_status: 'unconfirmed', turn_status: 'unconfirmed',
        active_turn_cleared: true, prior_success_turn_preserved: true,
      }));
    }
    const continued = page.waitForResponse(isFinalExecutionResponse, { timeout: 240000 });
    await send(page, '只看前2个产品');
    const body = await (await continued).json(); const result = querySnapshot(body.turn.snapshot);
    expect(body.history.id).toBe(input.ranked_history_id);
    expect(result.rows.map(row => [String(row[0]), Number(row[1])])).toEqual(reference.top_products.slice(0, 2).map((row: unknown[]) => [String(row[0]), Number(row[1])]));
    await page.goto(input.analysis_url); await expect(page.locator('.analysis-report h2')).toBeVisible();
    await page.goto(input.saved_url); await expect(page.getByRole('table')).toBeVisible();
    const requery = page.waitForResponse(isFinalExecutionResponse, { timeout: 240000 });
    await page.getByRole('button', { name: '重新查询当前数据', exact: true }).click();
    const newBody = await (await requery).json(); querySnapshot(newBody.turn.snapshot);
    expect(newBody.history.id).not.toBe(input.ranked_history_id);
    await expect(page.getByRole('button', { name: '另存成果', exact: true })).toBeVisible();
    const newUrl = page.url();
    await page.goto(input.saved_url); page.on('dialog', dialog => dialog.accept());
    await page.getByRole('button', { name: '删除成果', exact: true }).click();
    await page.goto(newUrl); await expect(page.getByRole('table')).toBeVisible();
    await page.getByRole('button', { name: '退出登录', exact: true }).click();
    evidence.r3_after_restart = { top_n_continuation_reference: true, committed_analysis_after_expiry: true, requery_new_history: true, delete_saved_keeps_history: true, new_login_blank: true };
    if (input.interrupted_execution) evidence.r4_after_restart = {
      interrupted_execution_visible_as_unconfirmed: true, previous_success_continued: true,
      api_process_killed_before_restart: true,
    };
    evidence.status = 'passed';
  } catch (error) { evidence.status = 'failed'; evidence.step = 'r3-restart'; evidence.error_type = (error as Error).name; throw new Error('R3重启验收未通过，请检查私有报告。'); }
  finally { writeFileSync('/reports/browser.json', JSON.stringify(evidence, null, 2)); }
});
