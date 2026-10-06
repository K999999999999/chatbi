import { useEffect } from 'react';

type PdfSource = {
  kind: 'analysis';
  question?: unknown;
  result_time?: unknown;
  saved_time?: unknown;
  export_time?: unknown;
  result: unknown;
};

export type PdfRenderRequest = { source: PdfSource; render_hash: string };
type Cell = string | number | boolean | null;
type PdfTask = { task_id: string; status: 'completed' | 'failed' | 'skipped'; columns: string[];
  rows: Cell[][]; row_count: number; truncated: boolean; error: string | null; metadata?: Record<string, unknown> };
type PdfProduct = { product_name: string; change: string; classification: string; effect_on_metric: string;
  factors: { name: string; amount: string; effect_on_metric: string }[] };
type PdfAttribution = { metric_name: string; comparison_period: string; current_period: string;
  comparison_value: string; current_value: string; total_change: string; direction: string;
  omitted_product_count: number; products: PdfProduct[] };
type PdfReport = { title: string; executive_summary: string; key_findings: string[]; trend_judgment: string;
  root_causes: string[]; action_suggestions: string[]; evidence_task_ids: string[];
  incomplete_tasks: { task_id: string; reasons: string[] }[]; attribution?: PdfAttribution };
type ParsedReport = { report: PdfReport; tasks: PdfTask[]; question: string; resultTime: string;
  savedTime: string; exportTime: string; warnings: string[] };
type TaskCoverage = { task_id: string; column_count: number; row_count: number; table_blocks: number; rendered_rows: number };
export type PdfManifest = { version: 1; render_hash: string; block_ids: string[]; tasks: TaskCoverage[];
  product_count: number; factor_count: number; attribution_chart: boolean };

const directionNames: Record<string, string> = {
  increase: '增加目标指标', decrease: '降低目标指标', unchanged: '目标指标无变化',
  increases_target_metric: '增加目标指标', decreases_target_metric: '降低目标指标',
  no_change_to_target_metric: '目标指标无变化',
};
const classificationNames: Record<string, string> = { continuing: '持续产品', new: '新增产品', discontinued: '退出产品' };
const incompleteNames: Record<string, string> = {
  failed: '查询任务失败', skipped: '查询任务因依赖未执行', empty_result: '查询任务没有返回数据', truncated: '查询任务结果已截断',
};

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${label}结构无效`);
  return value as Record<string, unknown>;
}
function text(value: unknown, label: string): string {
  if (typeof value !== 'string') throw new Error(`${label}文字无效`);
  return value;
}
function stringList(value: unknown, label: string): string[] {
  if (!Array.isArray(value) || !value.every(item => typeof item === 'string')) throw new Error(`${label}列表无效`);
  return value as string[];
}
function decimal(value: unknown, label: string): string {
  const result = text(value, label);
  if (!/^-?\d+(?:\.\d+)?$/.test(result)) throw new Error(`${label}数值无效`);
  return result;
}
function parseTask(value: unknown): PdfTask {
  const task = record(value, '查询任务');
  if (!['completed', 'failed', 'skipped'].includes(String(task.status))) throw new Error('查询任务状态无效');
  const columns = stringList(task.columns, '查询任务列');
  if (!Array.isArray(task.rows) || task.rows.length > 100) throw new Error('查询任务行无效');
  const rows = task.rows.map(row => {
    if (!Array.isArray(row) || row.length !== columns.length || row.some(cell =>
      cell !== null && typeof cell !== 'string' && typeof cell !== 'boolean' && !(typeof cell === 'number' && Number.isFinite(cell)))) {
      throw new Error('查询任务单元格无效');
    }
    return row as Cell[];
  });
  if (!Number.isSafeInteger(task.row_count) || Number(task.row_count) < rows.length || typeof task.truncated !== 'boolean') {
    throw new Error('查询任务返回范围无效');
  }
  const error = task.error === null || task.error === undefined ? null
    : typeof task.error === 'string' ? task.error
      : text(record(task.error, '查询任务错误').message, '查询任务错误');
  const metadata = task.result_metadata == null ? undefined : record(task.result_metadata, '查询口径');
  return { task_id: text(task.task_id, '查询任务编号'), status: task.status as PdfTask['status'], columns, rows,
    row_count: Number(task.row_count), truncated: task.truncated, error, ...(metadata ? { metadata } : {}) };
}
function parseAttribution(value: unknown): PdfAttribution {
  const attribution = record(value, '归因');
  if (!Array.isArray(attribution.products) || !Number.isSafeInteger(attribution.omitted_product_count)
    || Number(attribution.omitted_product_count) < 0) throw new Error('归因覆盖范围无效');
  const products = attribution.products.map(value => {
    const product = record(value, '产品归因');
    if (!Array.isArray(product.factors)) throw new Error('因素归因无效');
    return { product_name: text(product.product_name, '产品名称'), change: decimal(product.change, '产品贡献'),
      classification: text(product.classification, '产品分类'), effect_on_metric: text(product.effect_on_metric, '产品贡献方向'),
      factors: product.factors.map(value => {
        const factor = record(value, '因素归因');
        return { name: text(factor.name, '因素名称'), amount: decimal(factor.amount, '因素贡献'),
          effect_on_metric: text(factor.effect_on_metric, '因素贡献方向') };
      }) };
  });
  return { metric_name: text(attribution.metric_name, '归因指标'), comparison_period: text(attribution.comparison_period, '对比期间'),
    current_period: text(attribution.current_period, '当前期间'), comparison_value: decimal(attribution.comparison_value, '对比值'),
    current_value: decimal(attribution.current_value, '当前值'), total_change: decimal(attribution.total_change, '期间变化'),
    direction: text(attribution.direction, '期间变化方向'), omitted_product_count: Number(attribution.omitted_product_count), products };
}
function parseReport(source: PdfSource): ParsedReport {
  if (source.kind !== 'analysis') throw new Error('PDF 仅支持完成的经营分析快照');
  const result = record(source.result, '分析结果');
  const raw = record(result.report, '分析报告');
  if (!Array.isArray(result.task_results)) throw new Error('查询证据列表无效');
  const incomplete = raw.incomplete_tasks;
  if (!Array.isArray(incomplete)) throw new Error('证据限制列表无效');
  const incompleteTasks = incomplete.map(value => {
    const task = record(value, '证据限制');
    return { task_id: text(task.task_id, '证据限制任务编号'), reasons: stringList(task.reasons, '证据限制原因') };
  });
  const report: PdfReport = {
    title: text(raw.title, '报告标题'), executive_summary: text(raw.executive_summary, '执行摘要'),
    key_findings: stringList(raw.key_findings, '关键发现'), trend_judgment: text(raw.trend_judgment, '趋势判断'),
    root_causes: stringList(raw.root_causes, '原因分析'), action_suggestions: stringList(raw.action_suggestions, '行动建议'),
    evidence_task_ids: stringList(raw.evidence_task_ids, '引用任务'), incomplete_tasks: incompleteTasks,
    ...(raw.attribution === undefined ? {} : { attribution: parseAttribution(raw.attribution) }),
  };
  const tasks = result.task_results.map(parseTask);
  if (new Set(tasks.map(task => task.task_id)).size !== tasks.length) throw new Error('查询任务编号重复');
  if (report.evidence_task_ids.some(id => !tasks.some(task => task.task_id === id && task.status === 'completed'))) {
    throw new Error('报告引用了不可用查询任务');
  }
  if (incompleteTasks.some(item => !tasks.some(task => task.task_id === item.task_id))) throw new Error('证据限制引用了不存在的任务');
  const warnings: string[] = [];
  const listedIncomplete = new Set<string>();
  for (const item of incompleteTasks) {
    const task = tasks.find(value => value.task_id === item.task_id);
    const reasons = item.reasons
      .filter(reason => !(task?.status === 'failed' && reason === 'failed')
        && !(task?.status === 'skipped' && reason === 'skipped'))
      .map(reason => incompleteNames[reason] ?? reason);
    if (task?.status === 'failed') reasons.unshift(`查询任务失败${task.error ? `，${task.error}` : ''}`);
    else if (task?.status === 'skipped') reasons.unshift(`查询任务因依赖未执行${task.error ? `，${task.error}` : ''}`);
    warnings.push(`${item.task_id}：${reasons.join('；')}`);
    listedIncomplete.add(item.task_id);
  }
  for (const task of tasks) {
    if (listedIncomplete.has(task.task_id)) continue;
    if (task.status === 'failed') warnings.push(`${task.task_id}：查询任务失败${task.error ? `，${task.error}` : ''}`);
    else if (task.status === 'skipped') warnings.push(`${task.task_id}：查询任务因依赖未执行${task.error ? `，${task.error}` : ''}`);
    else if (task.rows.length === 0) warnings.push(`${task.task_id}：查询任务没有返回数据`);
    if (task.truncated) warnings.push(`${task.task_id}：仅包含快照已返回的 ${task.rows.length} 行，结果可能截断`);
  }
  const exportTime = text(source.export_time, '导出时间');
  return { report, tasks, question: typeof source.question === 'string' ? source.question : '原分析问题未保存',
    resultTime: typeof source.result_time === 'string' ? source.result_time : '原报告完成时间未保存',
    savedTime: typeof source.saved_time === 'string' ? source.saved_time : '', exportTime, warnings };
}
function expectedBlockIds(report: PdfReport): string[] {
  return ['title', 'executive-summary', 'key-findings', 'trend-judgment', 'root-causes', 'action-suggestions',
    ...(report.attribution ? ['attribution'] : []), 'evidence', 'limitations'];
}
function expectedCoverage(parsed: ParsedReport, renderHash: string): PdfManifest {
  const tasks = parsed.tasks.map(task => {
    const tableBlocks = Math.ceil(task.columns.length / 2);
    return { task_id: task.task_id, column_count: task.columns.length, row_count: task.rows.length,
      table_blocks: tableBlocks, rendered_rows: tableBlocks * task.rows.length };
  });
  const products = parsed.report.attribution?.products ?? [];
  return { version: 1, render_hash: renderHash, block_ids: expectedBlockIds(parsed.report), tasks,
    product_count: products.length, factor_count: products.reduce((sum, product) => sum + product.factors.length, 0),
    attribution_chart: products.length > 0 };
}
function taskCoverageFromDOM(root: HTMLElement, parsed: ParsedReport, renderHash: string): PdfManifest {
  const blocks = [...root.querySelectorAll<HTMLElement>('[data-pdf-block]')].map(item => item.dataset.pdfBlock ?? '');
  const taskOrder = new Map(parsed.tasks.map((task, index) => [task.task_id, index]));
  const tasks = [...root.querySelectorAll<HTMLElement>('[data-pdf-task]')].map(item => ({
    task_id: item.dataset.pdfTask ?? '', column_count: item.querySelectorAll('[data-pdf-column-index]').length,
    row_count: Number(item.dataset.sourceRowCount), table_blocks: item.querySelectorAll('[data-pdf-table]').length,
    rendered_rows: item.querySelectorAll('tbody tr[data-pdf-row-index]').length,
  })).sort((left, right) => (taskOrder.get(left.task_id) ?? Number.MAX_SAFE_INTEGER) - (taskOrder.get(right.task_id) ?? Number.MAX_SAFE_INTEGER));
  return { version: 1, render_hash: renderHash, block_ids: blocks, tasks,
    product_count: root.querySelectorAll('[data-pdf-product]').length,
    factor_count: root.querySelectorAll('[data-pdf-factor]').length,
    attribution_chart: root.querySelector('[data-pdf-attribution-chart]') !== null };
}
function sameCoverage(left: PdfManifest, right: PdfManifest): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}
function displayCell(value: Cell): string {
  if (value === null) return 'NULL（无数据）';
  if (value === '') return '空字符串';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  return String(value);
}
function metadataLines(metadata?: Record<string, unknown>): string[] {
  if (!metadata) return ['指标定义、单位和时间范围未保存在此任务快照中。'];
  const lines: string[] = [];
  const columns = Array.isArray(metadata.columns) ? metadata.columns : [];
  columns.forEach((value, index) => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return;
    const column = value as Record<string, unknown>;
    const title = typeof column.semantic_name === 'string' ? column.semantic_name
      : typeof column.name === 'string' ? column.name : `第${index + 1}列`;
    if (typeof column.definition === 'string' && column.definition) lines.push(`${title}：${column.definition}`);
    const unit = column.unit;
    if (unit && typeof unit === 'object' && !Array.isArray(unit) && typeof (unit as Record<string, unknown>).label === 'string') {
      lines.push(`${title}单位：${String((unit as Record<string, unknown>).label)}`);
    }
  });
  const scope = metadata.scope;
  if (scope && typeof scope === 'object' && !Array.isArray(scope)) {
    const value = scope as Record<string, unknown>;
    if (value.time_status === 'confirmed' && value.time && typeof value.time === 'object') {
      const time = value.time as Record<string, unknown>;
      lines.push(`查询时间：${String(time.start ?? '未知')} 至 ${String(time.end_exclusive ?? '未知')} 前 · ${String(time.time_basis ?? '口径未保存')}`);
    } else if (value.time_status === 'unbounded') lines.push('查询时间：未限定时间范围。');
    else lines.push('查询时间范围未完整确认。');
    for (const key of ['filters', 'grouping', 'warnings']) {
      const entry = value[key];
      if (Array.isArray(entry) && entry.length) lines.push(`${key === 'filters' ? '筛选' : key === 'grouping' ? '分组' : '范围提示'}：${JSON.stringify(entry)}`);
    }
  } else lines.push('查询时间与筛选范围未保存在此任务快照中。');
  return lines.length ? lines : ['未保存可用的指标定义、单位或查询范围。'];
}
function listSection(title: string, block: string, lines: string[]) {
  return <section className="pdf-section" data-pdf-block={block}><h2>{title}</h2>
    {lines.length ? <ul>{lines.map((line, index) => <li key={index}>{line}</li>)}</ul> : <p>未提供内容。</p>}</section>;
}
function exponentMagnitude(value: string): { sign: number; exponent: number; mantissa: number } {
  const sign = value.startsWith('-') ? -1 : 1;
  const absolute = value.replace(/^-/, '');
  const [whole, fraction = ''] = absolute.split('.');
  const digits = whole + fraction;
  const first = digits.search(/[1-9]/);
  if (first < 0) return { sign: 0, exponent: -Infinity, mantissa: 0 };
  const significant = digits.slice(first, first + 15);
  return { sign, exponent: whole.length - first - 1, mantissa: Number(significant) / 10 ** (significant.length - 1) };
}
function relativeWidth(value: string, all: string[]): number {
  const target = exponentMagnitude(value);
  const largest = all.map(exponentMagnitude).reduce((left, right) =>
    right.exponent > left.exponent || (right.exponent === left.exponent && right.mantissa > left.mantissa) ? right : left);
  if (!target.sign || !largest.sign) return 0;
  const difference = target.exponent - largest.exponent;
  return Math.max(1, Math.min(100, target.mantissa / largest.mantissa * (difference < -300 ? 0 : 10 ** difference) * 100));
}

function Attribution({ attribution }: { attribution: PdfAttribution }) {
  const products = attribution.products;
  const values = products.map(product => product.change);
  const maxWidth = Math.max(...values.map(value => relativeWidth(value, values)), 1);
  return <section className="pdf-section pdf-attribution" data-pdf-block="attribution">
    <h2>两期指标归因与产品因素</h2>
    <p><strong>{attribution.metric_name}</strong>：{attribution.comparison_period} 为 {attribution.comparison_value}，
      {attribution.current_period} 为 {attribution.current_value}；变化 {attribution.total_change}，{directionNames[attribution.direction] ?? '方向未确认'}。</p>
    {attribution.omitted_product_count > 0 && <p className="pdf-warning">报告快照另有 {attribution.omitted_product_count} 个产品未返回贡献明细；本文件不补查。</p>}
    {products.length > 0 && <div className="pdf-contribution-chart" data-pdf-attribution-chart>
      <h3>产品变化贡献图</h3><p className="pdf-muted">条形长度按返回贡献的相对数值比例绘制；正负方向以颜色和文字标示。</p>
      {products.map((product, index) => {
        const magnitude = relativeWidth(product.change, values);
        const positive = !product.change.startsWith('-') && product.change !== '0';
        return <div className="pdf-contribution-row" key={index} data-pdf-product>
          <div className="pdf-contribution-label">{product.product_name}<small>{classificationNames[product.classification] ?? '分类未确认'} · {directionNames[product.effect_on_metric] ?? '方向未确认'} · {product.change}</small></div>
          <div className="pdf-contribution-track"><span className={positive ? 'positive' : 'negative'} style={{ width: `${magnitude / maxWidth * 100}%` }}/></div>
        </div>;
      })}
    </div>}
    <h3>全部已返回产品与因素明细</h3>
    {products.length ? <table className="pdf-data-table pdf-attribution-table"><thead><tr><th>产品</th><th>产品变化贡献</th><th>因素</th><th>因素贡献</th><th>对目标指标的影响</th></tr></thead>
      <tbody>{products.flatMap((product, productIndex) => product.factors.length
        ? product.factors.map((factor, factorIndex) => <tr key={`${productIndex}-${factorIndex}`} data-pdf-factor>
          <td>{factorIndex === 0 ? `${product.product_name}（${classificationNames[product.classification] ?? '分类未确认'}）` : ''}</td>
          <td>{factorIndex === 0 ? `${product.change} · ${directionNames[product.effect_on_metric] ?? '方向未确认'}` : ''}</td>
          <td>{factor.name}</td><td>{factor.amount}</td><td>{directionNames[factor.effect_on_metric] ?? '方向未确认'}</td></tr>)
        : [<tr key={`${productIndex}-empty`}><td>{product.product_name}（{classificationNames[product.classification] ?? '分类未确认'}）</td>
          <td>{product.change}</td><td colSpan={3}>没有已返回因素明细。</td></tr>])}</tbody></table>
      : <p>报告快照没有返回产品贡献明细。</p>}
  </section>;
}

function EvidenceTask({ task }: { task: PdfTask }) {
  const blocks = [];
  for (let start = 0; start < task.columns.length; start += 2) blocks.push(start);
  const metadata = metadataLines(task.metadata);
  return <section className="pdf-task" data-pdf-task={task.task_id} data-source-row-count={task.rows.length}>
    <h3>{task.task_id} · {{ completed: '已完成', failed: '失败', skipped: '跳过' }[task.status]}</h3>
    <p>返回 {task.rows.length} 行 / {task.row_count} 行{task.truncated ? ' · 结果已截断' : ''}；共 {task.columns.length} 列。</p>
    {task.error && task.status !== 'completed' && <p className="pdf-warning">任务说明：{task.error}</p>}
    <div className="pdf-task-metadata">{metadata.map((line, index) => <p key={index}>{line}</p>)}</div>
    {!blocks.length ? <p>该任务没有可展示的数据列。</p> : blocks.map(start => {
      const selected = task.columns.map((name, offset) => ({ name, index: start + offset })).slice(0, 2);
      return <table className="pdf-data-table pdf-evidence-table" data-pdf-table key={start}>
        <thead><tr><th>原行号</th>{selected.map(column => <th data-pdf-column-index={column.index} key={column.index}>第{column.index + 1}列 · {column.name}</th>)}</tr></thead>
        <tbody>{task.rows.length ? task.rows.map((row, rowIndex) => <tr data-pdf-row-index={rowIndex + 1} key={rowIndex}>
          <td>{rowIndex + 1}</td>{selected.map(column => <td key={column.index}>{displayCell(row[column.index])}</td>)}</tr>)
          : <tr><td>—</td><td colSpan={selected.length}>该任务没有返回数据行。</td></tr>}</tbody>
      </table>;
    })}
  </section>;
}

export function PdfReport({ request }: { request: PdfRenderRequest }) {
  const parsed = parseReport(request.source);
  const expected = expectedCoverage(parsed, request.render_hash);
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        await document.fonts.ready;
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        if (!document.fonts.check('12px "ChatBI Export Noto CJK SC"', '经营分析报告 中文')) throw new Error('中文字体不可用');
        const root = document.querySelector<HTMLElement>('.pdf-report');
        if (!root || root.scrollWidth > root.clientWidth || [...root.querySelectorAll<HTMLElement>('*')].some(item =>
          item.scrollWidth > item.clientWidth + 2 && !item.matches('.pdf-contribution-track'))) throw new Error('PDF 页面存在横向溢出');
        const actual = taskCoverageFromDOM(root, parsed, request.render_hash);
        if (!sameCoverage(expected, actual)) throw new Error('PDF 内容 coverage 与成功快照不一致');
        if (active) window.__chatbiRenderState = { status: 'ready', manifest: actual };
      } catch (error) {
        if (active) window.__chatbiRenderState = { status: 'failed', code: 'PDF_RENDER_FAILED',
          error: error instanceof Error ? error.message : 'PDF 未能完整渲染' };
      }
    })();
    return () => { active = false; };
  }, [expected, parsed, request.render_hash]);

  const report = parsed.report;
  const evidenceTasks = report.evidence_task_ids.map(id => parsed.tasks.find(task => task.task_id === id)).filter((task): task is PdfTask => !!task);
  const otherTasks = parsed.tasks.filter(task => !report.evidence_task_ids.includes(task.task_id));
  return <main className="pdf-report" data-pdf-render="report">
    <header className="pdf-cover" data-pdf-block="title"><p className="pdf-kicker">ChatBI · 经营分析报告</p><h1>{report.title}</h1>
      <dl><dt>原分析问题</dt><dd>{parsed.question}</dd><dt>报告完成时间</dt><dd>{parsed.resultTime}</dd>
        {parsed.savedTime && <><dt>成果保存时间</dt><dd>{parsed.savedTime}</dd></>}
        <dt>导出时间</dt><dd>{parsed.exportTime}</dd></dl></header>
    <section className="pdf-section" data-pdf-block="executive-summary"><h2>摘要</h2><p>{report.executive_summary}</p></section>
    {listSection('关键发现', 'key-findings', report.key_findings)}
    <section className="pdf-section" data-pdf-block="trend-judgment"><h2>趋势判断</h2><p>{report.trend_judgment}</p></section>
    {listSection('原因分析', 'root-causes', report.root_causes)}
    {listSection('行动建议', 'action-suggestions', report.action_suggestions)}
    {report.attribution && <Attribution attribution={report.attribution}/>}
    <section className="pdf-section pdf-evidence" data-pdf-block="evidence"><h2>证据附录</h2>
      <p>报告引用任务：{report.evidence_task_ids.length ? report.evidence_task_ids.join('、') : '报告未引用查询任务'}。</p>
      <p className="pdf-muted">以下仅展示成功分析快照中已返回的任务数据、列口径与时间范围；未执行新查询。</p>
      {evidenceTasks.map(task => <EvidenceTask task={task} key={task.task_id}/>)}
      {otherTasks.length > 0 && <><h3>未被报告引用的已返回任务</h3><p>以下任务保留其状态与限制，不能作为报告已引用的证据。</p>
        {otherTasks.map(task => <EvidenceTask task={task} key={task.task_id}/>)}</>}
    </section>
    <section className="pdf-section" data-pdf-block="limitations"><h2>证据完整性与限制</h2>
      {parsed.warnings.length ? <ul>{parsed.warnings.map((warning, index) => <li className="pdf-warning" key={index}>{warning}</li>)}</ul>
        : <p>引用的查询任务已保存在分析快照中，未发现失败、跳过、空结果或截断标记。</p>}
    </section>
    <footer className="pdf-document-footer">由已保存的成功分析快照生成 · 不重新查询、不调用模型 · 导出时间：{parsed.exportTime}</footer>
  </main>;
}

export function createPdfManifest(request: PdfRenderRequest): PdfManifest {
  return expectedCoverage(parseReport(request.source), request.render_hash);
}
