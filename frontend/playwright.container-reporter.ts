import type { Reporter, TestCase, TestResult, FullResult } from '@playwright/test/reporter';
export default class ContainerReporter implements Reporter {
  onTestEnd(test: TestCase, result: TestResult) { console.log(`${result.status}: ${test.title}`); }
  onEnd(result: FullResult) { console.log(`容器浏览器验收：${result.status}；账号清理由外层验收入口核实。`); }
}
