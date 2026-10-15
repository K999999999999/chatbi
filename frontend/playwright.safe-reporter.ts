import type { FullResult, Reporter, TestCase, TestResult } from '@playwright/test/reporter';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { publishExclusiveJson } from './test-support/exclusive-report';
import { captureSourceIdentity } from './test-support/source-identity';

type Counts = { total: number; passed: number; failed: number; errors: number; skipped: number };

export default class SafeReporter implements Reporter {
  private counts: Counts = { total: 0, passed: 0, failed: 0, errors: 0, skipped: 0 };

  onTestEnd(test: TestCase, result: TestResult) {
    this.counts.total += 1;
    if (result.status === 'passed') this.counts.passed += 1;
    else if (result.status === 'skipped') this.counts.skipped += 1;
    else if (result.status === 'interrupted') this.counts.errors += 1;
    else this.counts.failed += 1;
    console.log(`${result.status}: ${test.title}`);
  }

  async onEnd(result: FullResult): Promise<{ status: FullResult['status'] }> {
    const reportRoot = resolve('..', 'reports/browser-real');
    const runDirectory = process.env.CHATBI_REAL_E2E_REPORT_DIR;
    const runId = process.env.CHATBI_REAL_E2E_RUN_ID;
    let reportStatus: 'passed' | 'failed' | 'interrupted' | 'incomplete' = 'incomplete';
    let cleanupStatus: 'passed' | 'failed' | 'not_run' = 'not_run';
    try {
      if (!runDirectory || !runId) throw new Error('运行身份缺失');
      const start = JSON.parse(readFileSync(resolve(runDirectory, 'start.json'), 'utf8'));
      const evidence = JSON.parse(readFileSync(resolve(runDirectory, 'browser.json'), 'utf8'));
      const cleanup = JSON.parse(readFileSync(resolve(runDirectory, 'cleanup.json'), 'utf8'));
      cleanupStatus = cleanup.disabled === true && cleanup.active_sessions === 0 ? 'passed' : 'failed';
      const sourceEnd = captureSourceIdentity(resolve('..'));
      const sourceStart = start.source_start;
      const provenanceConsistency = !sourceStart?.verified || !sourceEnd.verified
        ? 'unverified'
        : JSON.stringify(sourceStart) === JSON.stringify(sourceEnd) ? 'stable' : 'changed';

      if (result.status === 'interrupted' || this.counts.errors > 0) reportStatus = 'interrupted';
      else if (result.status !== 'passed' || this.counts.failed > 0 || cleanupStatus === 'failed') reportStatus = 'failed';
      else if (this.counts.total === 0 || this.counts.skipped > 0 || provenanceConsistency !== 'stable') reportStatus = 'incomplete';
      else reportStatus = 'passed';

      const counts = { ...this.counts };
      const machineSummary = {
        stats: {
          expected: counts.passed,
          unexpected: counts.failed,
          flaky: 0,
          skipped: counts.skipped,
          interrupted: counts.errors,
        },
      };
      writeFileSync(resolve(runDirectory, 'test-summary.json'), JSON.stringify(machineSummary), { mode: 0o600, flag: 'wx' });
      const report = {
        schema_version: 1,
        run_id: runId,
        kind: 'business-acceptance',
        scope: 'browser-real',
        started_at: start.started_at,
        finished_at: new Date().toISOString(),
        provenance: { version: 1, source_start: sourceStart, source_end: sourceEnd, consistency: provenanceConsistency },
        environment: { runner: 'host-browser', runtime: 'browser', browser: 'chromium' },
        status: reportStatus,
        business_acceptance_status: reportStatus,
        exit_code: reportStatus === 'passed' ? 0 : 1,
        cleanup_status: cleanupStatus,
        counts,
        counts_reason: null,
        steps: [{ name: 'browser', status: reportStatus === 'passed' ? 'passed' : reportStatus === 'interrupted' ? 'interrupted' : 'failed', counts }],
        artifacts: [`runs/${runId}`],
        evidence: { status: evidence.status ?? 'incomplete', cleanup },
      };
      publishExclusiveJson(resolve(reportRoot, `${runId}.json`), report);
      console.log(`真实浏览器验收报告：reports/browser-real/${runId}.json`);
    } catch {
      reportStatus = 'failed';
      console.log('真实验收证据未能安全发布；按失败处理。');
    }
    console.log(`真实浏览器验收：${reportStatus}`);
    return { status: reportStatus === 'passed' ? result.status : 'failed' };
  }
}
