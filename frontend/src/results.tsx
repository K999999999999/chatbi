export type Cell = string | number | boolean | null;
export type TableData = { columns: string[]; rows: Cell[][]; row_count: number; truncated: boolean };
export type QueryResult = TableData & { request_id: string; conversation_id: string; sql: string };

export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('响应结构无效');
  return value as Record<string, unknown>;
}
export function text(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) throw new Error('响应文字无效');
  return value;
}
export function strings(value: unknown): string[] {
  if (!Array.isArray(value) || !value.every(x => typeof x === 'string')) throw new Error('响应列表无效');
  return value;
}
export function tableData(value: unknown): TableData {
  const p = object(value);
  const columns = strings(p.columns);
  if (!Array.isArray(p.rows) || p.rows.length > 100 || !p.rows.every(row => Array.isArray(row)
      && row.length === columns.length && row.every(cell => cell === null || typeof cell === 'string'
        || typeof cell === 'boolean' || (typeof cell === 'number' && Number.isFinite(cell))))
      || !Number.isSafeInteger(p.row_count) || Number(p.row_count) < p.rows.length
      || typeof p.truncated !== 'boolean') throw new Error('响应表格无效');
  return { columns, rows: p.rows as Cell[][], row_count: Number(p.row_count), truncated: p.truncated };
}
export function queryResult(value: unknown): QueryResult {
  const p = object(value);
  if (p.row_count !== (p.rows as unknown[])?.length) throw new Error('响应行数无效');
  if (p.mode !== undefined && p.mode !== 'query') throw new Error('响应模式无效');
  return { ...tableData(p), request_id: text(p.request_id), conversation_id: text(p.conversation_id), sql: text(p.sql) };
}

export function ResultTable({ data }: { data: TableData }) {
  return <div className="result-table">
    <p className="result-meta">展示 {data.rows.length} 行{data.truncated ? ' · 结果已截断，仅展示部分数据（最多 100 行）。' : ''}</p>
    {!data.rows.length ? <p>查询成功，没有匹配的数据。</p> : <div className="table-scroll"><table>
      <thead><tr>{data.columns.map((name, i) => <th key={i}>{name}</th>)}</tr></thead>
      <tbody>{data.rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>
        {cell === null ? <span className="missing">NULL</span> : cell === '' ? <span className="missing">空字符串</span> : String(cell)}
      </td>)}</tr>)}</tbody>
    </table></div>}
  </div>;
}
