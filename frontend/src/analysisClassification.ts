export type ProductClassification = 'continuing' | 'new_product' | 'exited_product';

const canonical: Record<string, ProductClassification> = {
  continuing: 'continuing',
  new_product: 'new_product',
  new: 'new_product',
  exited_product: 'exited_product',
  discontinued: 'exited_product',
};

const labels: Record<ProductClassification, string> = {
  continuing: '持续产品',
  new_product: '新增产品',
  exited_product: '退出产品',
};

export function normalizeProductClassification(value: unknown): ProductClassification | null {
  return typeof value === 'string' && Object.prototype.hasOwnProperty.call(canonical, value)
    ? canonical[value]
    : null;
}

export function productClassificationLabel(value: unknown): string | undefined {
  const normalized = normalizeProductClassification(value);
  return normalized ? labels[normalized] : undefined;
}
