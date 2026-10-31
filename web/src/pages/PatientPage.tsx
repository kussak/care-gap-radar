import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router-dom";
import { api, ApiError, type PatientDetail } from "../api";
import { BriefPanel } from "../components/BriefPanel";
import { ErrorBox, GapBadge, Loading, RiskBar } from "../components/common";
import { PAYER_LABELS, ordinal } from "../labels";

export function PatientPage() {
  const { id = "" } = useParams();
  const { data: p, error } = useQuery({ queryKey: ["patient", id], queryFn: () => api.patient(id) });
  const worklistSearch = (useLocation().state as { worklistSearch?: string } | null)?.worklistSearch ?? "";

  return (
    <>
      <Link to={`/${worklistSearch}`} className="back">
        ← Back to worklist
      </Link>
      {error && (
        <ErrorBox error={error instanceof ApiError && error.status === 404 ? "Patient not found." : error} />
      )}
      {!p && !error && <Loading what="patient" />}
      {p && <PatientView p={p} />}
    </>
  );
}

function PatientView({ p }: { p: PatientDetail }) {
  const u = p.utilization;
  return (
    <>
      <section className="patient-header panel">
        <div>
          <h1>{p.display_name}</h1>
          <div className="muted">
            {p.age} y · {p.sex === "f" ? "Female" : p.sex === "m" ? "Male" : p.sex} ·{" "}
            {PAYER_LABELS[p.payer_category] ?? p.payer_category}
            {p.race && ` · ${p.race}`}
            {p.ethnicity && ` · ${p.ethnicity}`}
          </div>
        </div>
        <div className="patient-risk">
          <div className="stat-label">Predicted ED risk, next 6 months</div>
          <RiskBar percentile={p.risk?.percentile ?? null} />
        </div>
      </section>

      <div className="grid">
        <section className="panel">
          <h2>Open care gaps</h2>
          {p.open_gaps.length === 0 && <p className="muted">No open gaps.</p>}
          {p.open_gaps.map((g) => (
            <div key={g.gap_code} className="gap">
              <GapBadge code={g.gap_code} />
              <div>{g.gap_description}</div>
              <div className="evidence">Evidence: {g.evidence}</div>
            </div>
          ))}
        </section>

        <section className="panel">
          <h2>Risk drivers</h2>
          {!p.risk && <p className="muted">Not scored.</p>}
          {p.risk && (
            <>
              <p className="muted small">
                {ordinal(p.risk.percentile)} percentile · score {(p.risk.score * 100).toFixed(1)}% ·
                top features by SHAP
              </p>
              <ul className="drivers">
                {p.risk.top_drivers.map((d) => (
                  <li key={d.feature}>
                    <span className={`arrow ${d.direction}`} aria-label={d.direction === "up" ? "raises risk" : "lowers risk"}>
                      {d.direction === "up" ? "▲" : "▼"}
                    </span>
                    <span className="driver-label">{d.label}</span>
                    <span className="driver-value">{d.display_value}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>

        <section className="panel">
          <h2>Chronic conditions</h2>
          {p.conditions.length ? (
            <ul className="tags">
              {p.conditions.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">None on record.</p>
          )}
          <p className="small muted">Active medications: {p.active_med_count}</p>
        </section>

        <section className="panel">
          <h2>Utilization</h2>
          <table className="kv">
            <tbody>
              <tr><td>ED visits, 12 mo</td><td className="num">{u.ed_visits_12m}</td></tr>
              <tr><td>ED visits, 24 mo</td><td className="num">{u.ed_visits_24m}</td></tr>
              <tr><td>Inpatient stays, 12 mo</td><td className="num">{u.inpatient_visits_12m}</td></tr>
              <tr><td>Urgent care, 12 mo</td><td className="num">{u.urgent_care_visits_12m}</td></tr>
              <tr><td>Outpatient / primary care, 12 mo</td><td className="num">{u.outpatient_visits_12m}</td></tr>
              <tr><td>Claim cost, 12 mo</td><td className="num">${Math.round(u.total_claim_cost_12m).toLocaleString()}</td></tr>
              <tr><td>Days since last visit</td><td className="num">{u.days_since_last_encounter}</td></tr>
            </tbody>
          </table>
        </section>
      </div>

      <BriefPanel patientId={p.patient_id} />
    </>
  );
}
