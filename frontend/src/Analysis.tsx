import { useMemo, useState } from 'react';
import { object, strings, tableData, text, ResultView, type TableData } from './results';
import { DataChart } from './Chart';
import { plotNumber, type ChartPlan } from './chartPlan';
import { displayValue, roundedToZero, type DisplayColumn } from './numberFormat';
import type { ReportDraft } from './execution';

type Task = TableData & { task_id: string; status: string; error: string | null };
type Product = { product_name: string; change: string; classification: string; effect_on_metric: string; factors: { name: string; amount: string; effect_on_metric: string }[] };
type Attribution = { metric_name: string; comparison_period: string; current_period: string;
  comparison_value: string; current_value: string; total_change: string; direction: string; products: Product[]; omitted_product_count: number };
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
  const effect = (value: unknown) => { const s = text(value); if (!['increases_target_metric', 'decreases_target_metric', 'no_change_to_target_metric'].includes(s)) throw new Error('归因方向无效'); return s; };
  if (!['increase', 'decrease', 'unchanged'].includes(String(p.direction))) throw new Error('期间方向无效');
  if (p.reconciliation_passed !== true || !Number.isSafeInteger(p.omitted_product_count) || Number(p.omitted_product_count) < 0) throw new Error('归因对账响应无效');
  return { metric_name: text(p.metric_name), comparison_period: text(p.comparison_period), current_period: text(p.current_period),
    comparison_value: amount(p.comparison_value), current_value: amount(p.current_value), total_change: amount(p.total_change),
    direction: text(p.direction), omitted_product_count: Number(p.omitted_product_count), products: array(p.products).map(value => {
      const product = object(value);
      const classification = text(product.classification);
      if (!['continuing', 'new', 'discontinued'].includes(classification)) throw new Error('产品分类无效');
      return { product_name: text(product.product_name), change: amount(product.change), classification, effect_on_metric: effect(product.effect_on_metric),
        factors: array(product.factors).map(value => { const factor = object(value); return { name: text(factor.name), amount: amount(factor.amount), effect_on_metric: effect(factor.effect_on_metric) }; }) };
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
const effects: Record<string, string> = { increase: '增加目标指标', decrease: '降低目标指标', unchanged: '目标指标无变化', increases_target_metric: '增加目标指标', decreases_target_metric: '降低目标指标', no_change_to_target_metric: '目标指标无变化' };

// 已确认经营归因Contract仅支持这两个人民币金额指标。
function moneyColumn(metric: string): DisplayColumn {
  return { index: 0, name: metric, role: 'metric', certified: ['人民币毛利', '人民币净销售额'].includes(metric),
    semantic_name: metric, definition: null, unit: { key: 'CNY', label: '元' }, format: 'money' };
}
function contributionPlan(id: string, title: string, rows: { label: string; amount: string }[], column: DisplayColumn): ChartPlan | undefined {
  if (!column.certified || !rows.length) return;
  const values = rows.map(row => plotNumber(row.amount, column));
  if (values.some(value => value === undefined)) return;
  return { id, title, kind: 'contribution', truncated: false, series: [{ column,
    rawValues: rows.map(row => row.amount), points: rows.map((row, rowIndex) => ({ key: String(rowIndex), label: row.label, rowIndex, value: values[rowIndex]! })) }] };
}
function AttributionView({ data: a }: { data: Attribution }) {
  const [selected, setSelected] = useState(0);
  const product = a.products[selected];
  const column = useMemo(() => moneyColumn(a.metric_name), [a.metric_name]);
  const products = useMemo(() => contributionPlan('products', '主要产品变化贡献', a.products.map(p => ({ label: p.product_name, amount: p.change })), column), [a, column]);
  const factors = useMemo(() => contributionPlan('factors', `${product?.product_name ?? ''} · 因素贡献`, product?.factors.map(f => ({ label: f.name, amount: f.amount })) ?? [], column), [product, column]);
  const hasRoundedContribution = [a.comparison_value, a.current_value, a.total_change,
    ...a.products.flatMap(p => [p.change, ...p.factors.map(f => f.amount)])].some(value => roundedToZero(value, column));
  return <section className="attribution"><h3>{a.metric_name} · 两期归因</h3>
    <div className="metric-grid">{[[a.comparison_period, a.comparison_value], [a.current_period, a.current_value], ['期间变化', a.total_change]].map(([label, value]) =>
      <div key={label}><span>{label}</span><strong>{displayValue(value, column)}</strong><details className="raw-value"><summary>查看原始值</summary><code>{value}</code></details></div>)}</div>
    <p>期间变化方向：{effects[a.direction]}；对账已通过。</p>
    {hasRoundedContribution && <p className="result-meta">微小非零贡献按两位小数显示为0.00；请核对原始值，变化方向仍采用后端结论。</p>}
    {products && <details open><summary>产品贡献图</summary><DataChart plan={products}/></details>}
    {a.omitted_product_count > 0 && <p>另有 {a.omitted_product_count} 个产品未在主要贡献列表中展示。</p>}
    {a.products.length > 0 && <label>查看产品因素 <select value={selected} onChange={e => setSelected(Number(e.target.value))}>
      {a.products.map((p, i) => <option key={i} value={i}>{p.product_name}</option>)}</select></label>}
    {factors && <details open><summary>因素贡献图</summary><DataChart plan={factors}/></details>}
    {product && <p>{classifications[product.classification]}：{product.product_name}</p>}
    {product && !product.factors.length && <p>没有可用因素，不补造价格或成本贡献。</p>}
    <details open><summary>贡献表格</summary><div className="table-scroll"><table><thead><tr><th>产品</th><th>分类</th><th>变化贡献</th><th>方向</th></tr></thead><tbody>
      {a.products.map((p, i) => <tr key={i}><td>{p.product_name}</td><td>{classifications[p.classification]}</td><td>{displayValue(p.change, column)}<details className="raw-value"><summary>查看原始值</summary><code>{p.change}</code></details></td><td>{effects[p.effect_on_metric]}</td></tr>)}
    </tbody></table></div>{product && <ul>{product.factors.map((f, i) => <li key={i}><span>{f.name}：{displayValue(f.amount, column)} · {effects[f.effect_on_metric]}</span><details className="raw-value"><summary>查看原始值</summary><code>{f.amount}</code></details></li>)}</ul>}</details>
  </section>;
}
export function AnalysisReport({ result }: { result: AnalysisResult }) {
  const r = result.report; const a = r.attribution;
  return <div className="analysis-report"><h2>{r.title}</h2><p>{r.executive_summary}</p>
    <Lines title="关键发现" lines={r.key_findings}/><h3>趋势判断</h3><p>{r.trend_judgment}</p>
    <Lines title="原因分析" lines={r.root_causes}/><Lines title="行动建议" lines={r.action_suggestions}/>
    {a && <AttributionView data={a}/>}
    {r.incomplete_tasks.length > 0 && <section role="alert"><h3>证据不完整</h3>{r.incomplete_tasks.map((t, i) => <p key={i}>{t.task_id}：{t.reasons.join('；')}</p>)}</section>}
    <details><summary>查看查询任务证据</summary><p>报告引用：{r.evidence_task_ids.join('、')}</p>
      {result.task_results.map(task => <section key={task.task_id}><h3>{task.task_id} · {statuses[task.status]}</h3>
        {task.error && <p role="alert">{task.error}</p>}{task.status === 'completed' && <ResultView data={task}/>}</section>)}
    </details>
  </div>;
}

export function AnalysisDraft({ draft, interrupted }: { draft: ReportDraft; interrupted: boolean }) {
  const hasText = Object.values(draft).some(value =>
    typeof value === 'string' ? value.length > 0 : Array.isArray(value) && value.some(line => line.length > 0));
  if (!hasText) return null;
  return <div className="analysis-draft" aria-live="polite">
    <p className="draft-status" role="status">分析报告草稿生成中 · 尚未校验</p>
    {interrupted && <p role="status">连接中断，已保留当前草稿；重新连接后会同步服务端进度。</p>}
    {draft.title && <h2>{draft.title}</h2>}
    {draft.executive_summary && <p>{draft.executive_summary}</p>}
    {draft.key_findings && <Lines title="关键发现" lines={draft.key_findings}/>}
    {draft.trend_judgment && <><h3>趋势判断</h3><p>{draft.trend_judgment}</p></>}
    {draft.root_causes && <Lines title="原因分析" lines={draft.root_causes}/>}
    {draft.action_suggestions && <Lines title="行动建议" lines={draft.action_suggestions}/>}
  </div>;
}
