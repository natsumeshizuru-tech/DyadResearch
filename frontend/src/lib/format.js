export function dateLabel(value) {
  const text = String(value ?? "");
  return text.length === 8 ? `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6)}` : text;
}

export function percent(value, digits = 2) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${(numeric * 100).toFixed(digits)}%` : "--";
}

export function number(value, digits = 2) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toLocaleString("zh-CN", { maximumFractionDigits: digits }) : "--";
}

export function compact(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "--";
  if (Math.abs(numeric) >= 1e8) return `${(numeric / 1e8).toFixed(2)} 亿`;
  if (Math.abs(numeric) >= 1e4) return `${(numeric / 1e4).toFixed(2)} 万`;
  return number(numeric);
}
