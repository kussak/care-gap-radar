import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api, type GapCode } from "../api";
import { ErrorBox, GapBadge, Loading, RiskBar } from "../components/common";
import { SummaryHeader } from "../components/SummaryHeader";
import { GAP_LABELS, PAYER_LABELS, SEX_LABELS } from "../labels";

const PAGE_SIZE = 50;
const RISK_OPTIONS = [0, 50, 75, 90, 95];

export function WorklistPage() {
  // filters live in the URL so "back" from a patient restores the same view
  const [params, setParams] = useSearchParams();
  const gap = (params.get("gap") as GapCode | null) ?? undefined;
  const minRisk = Number(params.get("min_risk") ?? 0);
  const page = Number(params.get("page") ?? 0);
  const navigate = useNavigate();
  const { search } = useLocation();
  const open = (id: string) => navigate(`/patients/${id}`, { state: { worklistSearch: search } });

  const { data, error, isFetching } = useQuery({
    queryKey: ["worklist", gap, minRisk, page],
    queryFn: () =>
      api.worklist({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        gap,
        minRisk: minRisk > 0 ? minRisk : undefined,
      }),
    placeholderData: keepPreviousData,
  });

  const update = (changes: Record<string, string | undefined>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next);
  };

  const pages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <>
      <SummaryHeader />

      <section className="panel">
        <div className="toolbar">
          <h2>Worklist</h2>
          <label>
            Care gap
            <select value={gap ?? ""} onChange={(e) => update({ gap: e.target.value || undefined })}>
              <option value="">Any patient</option>
              {(Object.keys(GAP_LABELS) as GapCode[]).map((c) => (
                <option key={c} value={c}>
                  {GAP_LABELS[c]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Min risk percentile
            <select
              value={minRisk}
              onChange={(e) => update({ min_risk: e.target.value === "0" ? undefined : e.target.value })}
            >
              {RISK_OPTIONS.map((r) => (
                <option key={r} value={r}>
                  {r === 0 ? "Any" : `≥ ${r}th`}
                </option>
              ))}
            </select>
          </label>
          <span className="muted toolbar-count">
            {data ? `${data.total.toLocaleString()} patients` : ""}
            {isFetching && data ? " · updating…" : ""}
          </span>
        </div>

        {error && <ErrorBox error={error} />}
        {!data && !error && <Loading what="worklist" />}
        {data && (
          <div className="table-wrap">
            <table className="worklist">
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Age / sex</th>
                  <th>Payer</th>
                  <th>ED risk (6 mo)</th>
                  <th>Open gaps</th>
                  <th className="num">ED visits 12 mo</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((p) => (
                  <tr
                    key={p.patient_id}
                    className="clickable"
                    tabIndex={0}
                    onClick={() => open(p.patient_id)}
                    onKeyDown={(e) => e.key === "Enter" && open(p.patient_id)}
                  >
                    <td className="name">{p.display_name}</td>
                    <td>
                      {p.age} {SEX_LABELS[p.sex] ?? p.sex}
                    </td>
                    <td>{PAYER_LABELS[p.payer_category] ?? p.payer_category}</td>
                    <td>
                      <RiskBar percentile={p.risk_percentile} />
                    </td>
                    <td>
                      {p.open_gap_codes.length ? (
                        p.open_gap_codes.map((c) => <GapBadge key={c} code={c} />)
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td className="num">{p.ed_visits_12m}</td>
                  </tr>
                ))}
                {data.items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="muted empty">
                      No patients match these filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {pages > 1 && (
          <div className="pager">
            <button disabled={page === 0} onClick={() => update({ page: String(page - 1) })}>
              ← Previous
            </button>
            <span className="muted">
              Page {page + 1} of {pages}
            </span>
            <button disabled={page + 1 >= pages} onClick={() => update({ page: String(page + 1) })}>
              Next →
            </button>
          </div>
        )}
      </section>
    </>
  );
}
