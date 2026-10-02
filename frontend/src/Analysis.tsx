import { object, strings, tableData, text, ResultTable, type TableData } from './results';

type Task = TableData & { task_id: string; status: string; error: string | null };
type Product = { product_name: string; change: string; classification: string; factors: { name: string; amount: string }[] };
type Attribution = { metric_name: string; comparison_period: string; current_period: string;
  comparison_value: string; current_value: string; total_change: string; products: Product[]; omitted_product_count: number };
type Report = { title: string; executive_summary: string; key_findings: string[]; trend_judgment: string;
  root_causes: string[]; action_suggestions: string[]; evidence_task_ids: string[];
  incomplete_tasks: { task_id: string; reasons: string[] }[]; attribution?: Attribution };
export type AnalysisResult = { analysis_run_id: string; request_id: string; report: Report; task_results: Task[] };

function array(value: unknown): unknown[] {
  if (!Array.isArray(value)) throw new Error('分析响应列表无效');
  return value;
}
function attribution(value: unknown): Attribution {
  const p = object(value);
  const amount = (value: unknown) => { const s = text(value); if (!/^-?\d+(\.\d+)?$/.test(s)) throw new Error('归因数值无效'); return s; };
  if (p.reconciliation_passed !== true || !Number.isSafeInteger(p.omitted_product_count) || Number(p.omitted_product_count) < 0) throw new Error('归因对账响应无效');
  return { metric_name: text(p.metric_name), comparison_period: text(p.comparison_period), current_period: text(p.current_period),
    comparison_value: amount(p.comparison_value), current_value: amount(p.current_value), total_change: amount(p.total_change),
    omitted_product_count: Number(p.omitted_product_count), products: array(p.products).map(value => {
      const product = object(value);
      return { product_name: text(product.product_name), change: amount(product.change), classification: text(product.classification),
        factors: array(product.factors).map(value => { const factor = object(value); return { name: text(factor.name), amount: amount(factor.amount) }; }) };
    }) };
}
export function analysisResult(value: unknown, expectedId: string): AnalysisResult {
  const p = object(value); const r = object(p.report);
  if (p.mode !== 'analysis' || p.analysis_run_id !== expectedId) throw new Error('分析任务身份不一致');
  const tasks = array(p.task_results).map(value => {
    const task = object(value); const status = text(task.status);
    if (!['completed', 'failed', 'skipped'].includes(status)) throw new Error('任务状态无效');
    return { ...tableData(task), task_id: text(task.task_id), status,
      error: task.error === null ? null : text(object(task.error).message) };
  });
  const evidence = strings(r.evidence_task_ids);
  if (!evidence.every(id => tasks.some(task => task.task_id === id))) throw new Error('报告证据无效');
  return { analysis_run_id: expectedId, request_id: text(p.request_id), task_results: tasks,
    report: { title: text(r.title), executive_summary: text(r.executive_summary), key_findings: strings(r.key_findings),
      trend_judgment: text(r.trend_judgment), root_causes: strings(r.root_causes), action_suggestions: strings(r.action_suggestions),
      evidence_task_ids: evidence, incomplete_tasks: array(r.incomplete_tasks).map(value => {
        const task = object(value); return { task_id: text(task.task_id), reasons: strings(task.reasons) }; }),
      ...(r.attribution === undefined ? {} : { attribution: attribution(r.attribution) }) } };
}
const classifications: Record<string, string> = { continuing: '持续产品', new: '新增产品', discontinued: '退出产品' };
const statuses: Record<string, string> = { completed: '完成', failed: '失败', skipped: '跳过' };
function Lines({ title, lines }: { title: string; lines: string[] }) {
  return lines.length > 0 && <section><h3>{title}</h3><ul>{lines.map((line, i) => <li key={i}>{line}</li>)}</ul></section>;
}
export function AnalysisReport({ result }: { result: AnalysisResult }) {
  const r = result.report; const a = r.attribution;
  return <div className="analysis-report"><h2>{r.title}</h2><p>{r.executive_summary}</p>
    <Lines title="关键发现" lines={r.key_findings}/><h3>趋势判断</h3><p>{r.trend_judgment}</p>
    <Lines title="原因分析" lines={r.root_causes}/><Lines title="行动建议" lines={r.action_suggestions}/>
    {a && <section className="attribution"><h3>{a.metric_name} · 两期归因</h3>
      <div className="metric-grid"><div><span>{a.comparison_period}</span><strong>{a.comparison_value}</strong></div>
        <div><span>{a.current_period}</span><strong>{a.current_value}</strong></div><div><span>期间变化</span><strong>{a.total_change}</strong></div></div>
      <p className="result-meta">对账已通过；数值按后端返回展示。</p>
      {a.products.map((p, i) => <div className="product" key={i}><h4>{p.product_name} <span>{classifications[p.classification] ?? p.classification}</span></h4>
        <p>变化贡献：{p.change}</p><ul>{p.factors.map((f, j) => <li key={j}>{f.name}：{f.amount}</li>)}</ul></div>)}
      {a.omitted_product_count > 0 && <p>另有 {a.omitted_product_count} 个产品未在主要贡献列表中展示。</p>}
    </section>}
    {r.incomplete_tasks.length > 0 && <section role="alert"><h3>证据不完整</h3>{r.incomplete_tasks.map((t, i) => <p key={i}>{t.task_id}：{t.reasons.join('；')}</p>)}</section>}
    <details><summary>查看查询任务证据</summary><p>报告引用：{r.evidence_task_ids.join('、')}</p>
      {result.task_results.map(task => <section key={task.task_id}><h3>{task.task_id} · {statuses[task.status]}</h3>
        {task.error && <p role="alert">{task.error}</p>}{task.status === 'completed' && <ResultTable data={task}/>}</section>)}
    </details>
  </div>;
}
