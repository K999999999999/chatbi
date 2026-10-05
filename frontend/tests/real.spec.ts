import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync, readFileSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { login, send, isFinalExecutionResponse } from './helpers';
import { querySnapshot } from '../src/results';
import { analysisResult } from '../src/Analysis';

test('real Chrome login → model/RAG query → followup → two-period analysis', async ({ page, browser }) => {
  const root = resolve('..');
  const commit = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
  const dirty = execFileSync('git', ['status', '--porcelain'], { cwd: root, encoding: 'utf8' }).trim();
  if (dirty) throw new Error('真实验收只接受 clean candidate');
  const reference = JSON.parse(execFileSync('uv', ['run', '--locked', 'python', '-m', 'tests.browser_real_reference'], { cwd: root, encoding: 'utf8' }));
  const assetDirectory = resolve(root, 'frontend/dist/assets');
  const build = ['index.html', ...readdirSync(assetDirectory).map(name => `assets/${name}`)].sort().map(name => ({
    name, sha256: createHash('sha256').update(readFileSync(resolve(root, 'frontend/dist', name))).digest('hex'),
  }));
  const evidence: Record<string, unknown> = { username: process.env.CHATBI_REAL_E2E_USERNAME, commit, git_dirty: false, at: new Date().toISOString(), chrome: browser.version(), platform: process.platform, build, reference };
  const directory = resolve(root, 'reports/browser-real'); mkdirSync(directory, { recursive: true });
  const reportPath = resolve(directory, `${new Date().toISOString().replace(/[:.]/g, '-')}-${commit.slice(0, 7)}.json`);
  try {
    evidence.step = "login";
    await login(page, process.env.CHATBI_REAL_E2E_USERNAME!, process.env.CHATBI_REAL_E2E_PASSWORD!);
    evidence.step = "query";
    const firstResponse = page.waitForResponse(isFinalExecutionResponse, { timeout: 200000 });
    await send(page, '2025年2月已完成订单的人民币净销售额是多少？');
    evidence.query_response = await (await firstResponse).json();
    const first = querySnapshot((evidence.query_response as any).turn.snapshot); evidence.query = first;
    expect(Number(first.rows[0][0])).toBe(Number(reference.net_sales['2']));
    await expect(page.getByRole('table')).toHaveCount(1);
    evidence.step = "followup";
    const followupResponse = page.waitForResponse(isFinalExecutionResponse, { timeout: 200000 });
    await send(page, '改成2025年3月');
    evidence.followup_response = await (await followupResponse).json();
    const followup = querySnapshot((evidence.followup_response as any).turn.snapshot); evidence.followup = followup;
    expect((evidence.followup_response as any).history.id).toBe((evidence.query_response as any).history.id);
    expect(Number(followup.rows[0][0])).toBe(Number(reference.net_sales['3']));
    await expect(page.getByRole('table')).toHaveCount(2);
    evidence.step = 'analysis';
    await page.getByRole('button', { name: '经营分析', exact: true }).click();
    const responsePromise = page.waitForResponse(isFinalExecutionResponse, { timeout: 1250000 });
    await send(page, '分析2025年3月相比2025年2月的人民币毛利变化及产品因素贡献。');
    const response = await responsePromise; const body = await response.json(); evidence.analysis_response = body;
    const id = body.history.analysis_run_id;
    const analysis = analysisResult(body.turn.snapshot, id); evidence.analysis = analysis;
    expect(analysis.report.attribution).toEqual(expect.objectContaining({
      metric_name: reference.attribution.metric_name, comparison_value: reference.attribution.comparison_value,
      current_value: reference.attribution.current_value, total_change: reference.attribution.total_change,
      products: reference.attribution.products.map((p: Record<string, unknown>) => expect.objectContaining({
        product_name: p.product_name, change: p.change, classification: p.classification,
        factors: (p.factors as Record<string, unknown>[]).map(f => ({ name: f.name, amount: f.amount, effect_on_metric: f.effect_on_metric })) })),
    }));
    expect(analysis.task_results).toHaveLength(4);
    expect(analysis.task_results.every(task => task.status === 'completed' && !task.truncated)).toBe(true);
    await expect(page.locator('.analysis-report h2')).toBeVisible();
    await page.getByText('查看查询任务证据').click();
    await expect(page.getByText('查看查询任务证据').locator('..').getByRole('table')).toHaveCount(4);
    await page.getByRole('button', { name: '退出登录' }).click();
    await expect(page.getByRole('button', { name: '登录', exact: true })).toBeVisible();
    evidence.step = 'complete'; evidence.status = 'passed';
  } catch (error) {
    evidence.status = 'failed'; evidence.error_type = (error as Error).name;
    throw new Error('真实业务闭环未通过，请检查 ignored reports/browser-real 证据；不输出凭证或响应。');
  } finally { writeFileSync(reportPath, JSON.stringify(evidence, null, 2)); }
});
