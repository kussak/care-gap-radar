import type { GapCode } from "./api";

export const GAP_LABELS: Record<GapCode, string> = {
  DM_A1C: "Diabetes: no A1c",
  HTN_BP: "Hypertension: BP",
};

export const PAYER_LABELS: Record<string, string> = {
  medicaid: "Medicaid",
  medicare: "Medicare",
  private: "Private",
  none_other: "Uninsured / other",
};

export const SEX_LABELS: Record<string, string> = { f: "F", m: "M" };

export const pct = (x: number, digits = 1) => `${(x * 100).toFixed(digits)}%`;

export function ordinal(p: number): string {
  const n = Math.min(Math.floor(p), 99);
  const suffix = n % 100 >= 10 && n % 100 <= 20 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${suffix}`;
}
