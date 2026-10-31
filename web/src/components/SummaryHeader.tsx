import { useQuery } from "@tanstack/react-query";
import { api, type ModelCard } from "../api";
import { GAP_LABELS, pct } from "../labels";
import { ErrorBox } from "./common";

export function SummaryHeader() {
  const { data, error } = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  if (error) return <ErrorBox error={error} />;
  if (!data) return <div className="summary placeholder" />;

  return (
    <section className="summary">
      <div className="stats">
        <Stat label="Patients" value={data.patient_count.toLocaleString()} />
        <Stat label="With open gaps" value={data.patients_with_open_gaps.toLocaleString()} />
        <Stat label={GAP_LABELS.DM_A1C} value={data.gap_counts.DM_A1C} />
        <Stat label={GAP_LABELS.HTN_BP} value={data.gap_counts.HTN_BP} />
        <Stat label="Data as of" value={data.data_as_of} small />
      </div>
      {data.model && <ModelCardBox card={data.model} />}
    </section>
  );
}

function Stat({ label, value, small }: { label: string; value: string | number; small?: boolean }) {
  return (
    <div className="stat">
      <div className={small ? "stat-value date" : "stat-value"}>{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function ModelCardBox({ card }: { card: ModelCard }) {
  const [lo, hi] = card.auroc_delta_ci95;
  const signed = (x: number) => `${x >= 0 ? "+" : ""}${x.toFixed(3)}`;
  return (
    <div className="model-card">
      <div className="model-card-title">ED-risk model (6 months)</div>
      <table>
        <thead>
          <tr>
            <th />
            <th>AUROC</th>
            <th>PR-AUC</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Model</td>
            <td>{card.model.auroc.toFixed(3)}</td>
            <td>{card.model.pr_auc.toFixed(3)}</td>
          </tr>
          <tr>
            <td>Prior-ED baseline</td>
            <td>{card.baseline_prior_ed.auroc.toFixed(3)}</td>
            <td>{card.baseline_prior_ed.pr_auc.toFixed(3)}</td>
          </tr>
        </tbody>
      </table>
      <p className={card.beats_baseline ? "verdict good" : "verdict warn"}>
        {card.beats_baseline
          ? "Beats the baseline"
          : "Not clearly better than the baseline"}{" "}
        <span className="muted">
          (ΔAUROC 95% CI {signed(lo)} to {signed(hi)}; base rate {pct(card.base_rate_test)})
        </span>
      </p>
    </div>
  );
}
