import { writeFileSync } from 'node:fs';
import type { Reporter, TestCase, TestResult, FullResult } from '@playwright/test/reporter';
export default class ContainerReporter implements Reporter {
  private errors: { test: string; locations: string[] }[] = [];
  onTestEnd(test: TestCase, result: TestResult) {
    console.log(`${result.status}: ${test.title}`);
    if (result.status !== 'passed') this.errors.push({ test: test.title,
      locations: result.errors.flatMap(error => error.stack?.match(/container-real\.spec\.ts:\d+:\d+/g) ?? []) });
  }
  onEnd(result: FullResult) {
    writeFileSync('/reports/test-errors.json', JSON.stringify(this.errors));
    console.log(`容器浏览器验收：${result.status}；账号清理由外层验收入口核实。`);
  }
}
