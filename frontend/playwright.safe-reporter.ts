import type { Reporter, TestCase, TestResult, FullResult } from '@playwright/test/reporter';
// 真实验收不向控制台输出 assertion 内容、请求或凭证。
export default class SafeReporter implements Reporter {
  onTestEnd(test: TestCase, result: TestResult) { console.log(`${result.status}: ${test.title}`); }
  onEnd(result: FullResult) { console.log(`真实浏览器验收：${result.status}`); }
}
