// String-only decimal helpers. Financial values never pass through JS numbers,
// so nothing here can introduce binary floating-point error.

const DECIMAL_PATTERN = /^\d+(\.\d+)?$/;

/** Trim and strip thousands separators / a leading "$". Returns "" if empty. */
export function normalizeDecimal(input: string): string {
  return input.trim().replace(/^\$/, "").replace(/,/g, "");
}

export function isDecimalString(value: string): boolean {
  return DECIMAL_PATTERN.test(value);
}

/** Exact comparison of two non-negative decimal strings. */
export function compareDecimal(a: string, b: string): -1 | 0 | 1 {
  const [aInt, aFrac = ""] = a.split(".");
  const [bInt, bFrac = ""] = b.split(".");
  const intA = aInt.replace(/^0+(?=\d)/, "");
  const intB = bInt.replace(/^0+(?=\d)/, "");
  if (intA.length !== intB.length) return intA.length < intB.length ? -1 : 1;
  const width = Math.max(aFrac.length, bFrac.length);
  const left = intA + aFrac.padEnd(width, "0");
  const right = intB + bFrac.padEnd(width, "0");
  if (left === right) return 0;
  return left < right ? -1 : 1;
}

export function isZero(value: string): boolean {
  return compareDecimal(value, "0") === 0;
}

/** "7.25" (percent) → "0.0725" (fraction), by moving the decimal point. */
export function percentToFraction(percent: string): string {
  const [intPart, fracPart = ""] = percent.split(".");
  const digits = intPart.padStart(3, "0") + fracPart;
  const pointAt = digits.length - fracPart.length - 2;
  const whole = digits.slice(0, pointAt).replace(/^0+(?=\d)/, "");
  const frac = digits.slice(pointAt).replace(/0+$/, "");
  return frac ? `${whole}.${frac}` : whole;
}

/** "33000.00" → "$33,000.00". Input is a backend decimal string. */
export function formatCurrency(value: string): string {
  const negative = value.startsWith("-");
  const [intPart, fracPart = ""] = (negative ? value.slice(1) : value).split(".");
  const grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const cents = fracPart.padEnd(2, "0").slice(0, 2);
  return `${negative ? "−" : ""}$${grouped}.${cents}`;
}

/** "0.0725" (fraction) → "7.25%", for display. */
export function formatFractionAsPercent(fraction: string): string {
  const [intPart, fracPart = ""] = fraction.split(".");
  const digits = intPart + fracPart.padEnd(2, "0");
  const pointAt = intPart.length + 2;
  const whole = digits.slice(0, pointAt).replace(/^0+(?=\d)/, "");
  const frac = digits.slice(pointAt).replace(/0+$/, "");
  return `${frac ? `${whole}.${frac}` : whole}%`;
}
