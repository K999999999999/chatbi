import { writeFileSync } from 'node:fs';
import type { Reporter, TestCase, TestResult, FullResult } from '@playwright/test/reporter';
import { reportPath } from './test-support/report-path';
export default class ContainerReporter implements Reporter {
  private errors: { test: string; locations: string[] }[] = [];
  private counts = { total: 0, expected: 0, unexpected: 0, skipped: 0, interrupted: 0 };
  onTestEnd(test: TestCase, result: TestResult) {
    this.counts.total += 1;
    if (result.status === 'passed') this.counts.expected += 1;
    else if (result.status === 'skipped') this.counts.skipped += 1;
    else if (result.status === 'interrupted') this.counts.interrupted += 1;
    else this.counts.unexpected += 1;
    console.log(`${result.status}: ${test.title}`);
    if (result.status !== 'passed') this.errors.push({ test: test.title,
      locations: result.errors.flatMap(error => error.stack?.match(/container-real\.spec\.ts:\d+:\d+/g) ?? []) });
  }
  onEnd(result: FullResult) {
    writeFileSync(reportPath('test-errors.json'), JSON.stringify(this.errors));
    writeFileSync(reportPath('test-summary.json'), JSON.stringify({
      stats: { ...this.counts, flaky: 0 },
    }));
    console.log(`容器浏览器验收：${result.status}；账号清理由外层验收入口核实。`);
  }
}
