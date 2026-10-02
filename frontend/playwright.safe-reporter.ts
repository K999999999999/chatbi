import type { Reporter, TestCase, TestResult, FullResult } from '@playwright/test/reporter';
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

// 真实验收不向控制台输出 assertion 内容、请求或凭证。
export default class SafeReporter implements Reporter {
  onTestEnd(test: TestCase, result: TestResult) { console.log(`${result.status}: ${test.title}`); }
  async onEnd(result: FullResult): Promise<{ status: FullResult['status'] }> {
    let status = result.status;
    if (status === 'passed') {
      try {
        const directory = resolve('..', 'reports/browser-real');
        const username = process.env.CHATBI_REAL_E2E_USERNAME;
        const cleanup = JSON.parse(readFileSync(resolve(directory, `cleanup-${username}.json`), 'utf8'));
        if (cleanup.disabled !== true || cleanup.active_sessions !== 0) throw new Error('清理未通过');
        const reports = readdirSync(directory).filter(name => !name.startsWith('cleanup-') && name.endsWith('.json'));
        const name = reports.find(name => JSON.parse(readFileSync(resolve(directory, name), 'utf8')).username === username);
        if (!name) throw new Error('验收报告缺失');
        const path = resolve(directory, name); const evidence = JSON.parse(readFileSync(path, 'utf8'));
        evidence.cleanup = cleanup; evidence.suite_status = status;
        writeFileSync(path, JSON.stringify(evidence, null, 2));
      } catch { status = 'failed'; console.log('真实验收账号清理或证据核验失败。'); }
    }
    console.log(`真实浏览器验收：${status}`);
    return { status };
  }
}
