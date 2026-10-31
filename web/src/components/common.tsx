import type { GapCode } from "../api";
import { GAP_LABELS, ordinal } from "../labels";

export function RiskBar({ percentile }: { percentile: number | null }) {
  if (percentile === null) return <span className="muted">—</span>;
  const level = percentile >= 90 ? "high" : percentile >= 75 ? "mid" : "low";
  return (
    <div className="risk" title={`Predicted ED risk: ${ordinal(percentile)} percentile`}>
      <div className="risk-track">
        <div className={`risk-fill ${level}`} style={{ width: `${Math.max(percentile, 2)}%` }} />
      </div>
      <span className="risk-label">{ordinal(percentile)}</span>
    </div>
  );
}

export function GapBadge({ code }: { code: GapCode }) {
  return <span className={`badge gap-${code.toLowerCase()}`}>{GAP_LABELS[code]}</span>;
}

export function Loading({ what }: { what: string }) {
  return <p className="muted">Loading {what}…</p>;
}

export function ErrorBox({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="error-box" role="alert">
      {msg}
    </div>
  );
}
