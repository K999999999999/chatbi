export type DisplayFormat = 'money' | 'count' | 'ratio' | 'number' | 'raw';
export type DisplayColumn = { index: number; name: string; certified: boolean; role: string;
  semantic_name: string | null; definition: string | null; unit: { key: string; label: string } | null; format: DisplayFormat };

function decimal(value: unknown): { negative: boolean; digits: string; scale: number } | undefined {
  if (typeof value !== 'string' && typeof value !== 'number') return;
  const match = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(String(value));
  if (!match || match[2].length + (match[3]?.length ?? 0) > 10000) return;
  const exponent = Number(match[4] ?? 0);
  if (!Number.isSafeInteger(exponent) || Math.abs(exponent) > 1000) return;
  let digits = (match[2] + (match[3] ?? '')).replace(/^0+(?=\d)/, '');
  let scale = (match[3]?.length ?? 0) - exponent;
  if (scale < 0) { digits += '0'.repeat(-scale); scale = 0; }
  return { negative: match[1] === '-', digits, scale };
}

function grouped(integer: string): string { return integer.replace(/\B(?=(\d{3})+(?!\d))/g, ','); }

export function displayValue(value: unknown, column?: DisplayColumn): string {
  const raw = value === null ? '无数据' : value === '' ? '空字符串' : String(value);
  if (!column?.certified || column.role !== 'metric' || column.format === 'raw') return raw;
  const parsed = decimal(value);
  if (!parsed) return raw;
  let { digits, scale } = parsed;
  if (column.format === 'ratio') scale -= 2;
  if (scale < 0) { digits += '0'.repeat(-scale); scale = 0; }
  const target = column.format === 'money' || column.format === 'ratio' ? 2 : scale;
  if (column.format === 'count') {
    if (scale && !digits.endsWith('0'.repeat(scale))) return raw;
    digits = scale ? digits.slice(0, -scale) || '0' : digits;
    scale = 0;
  }
  let amount = BigInt(digits);
  const precision = column.format === 'count' ? 0 : target;
  if (scale > precision) {
    const divisor = 10n ** BigInt(scale - precision);
    amount = amount / divisor + (amount % divisor * 2n >= divisor ? 1n : 0n);
  } else if (scale < precision) amount *= 10n ** BigInt(precision - scale);
  const text = amount.toString().padStart(precision + 1, '0');
  const integer = precision ? text.slice(0, -precision) : text;
  const fraction = precision ? '.' + text.slice(-precision) : '';
  const suffix = column.unit ? (column.format === 'ratio' ? column.unit.label : ' ' + column.unit.label) : '';
  return (parsed.negative && amount !== 0n ? '-' : '') + grouped(integer) + fraction + suffix;
}

export function roundedToZero(value: unknown, column?: DisplayColumn): boolean {
  const parsed = decimal(value);
  return Boolean(parsed && BigInt(parsed.digits) !== 0n && /^(?:0\.00)(?:\s|%|$)/.test(displayValue(value, column)));
}
