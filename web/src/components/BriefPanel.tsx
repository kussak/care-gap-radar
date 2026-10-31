import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { api, type BriefResponse } from "../api";
import { ErrorBox } from "./common";

export function BriefPanel({ patientId }: { patientId: string }) {
  const [active, setActive] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: (refresh: boolean) => api.brief(patientId, refresh),
  });
  const result = mutation.data;

  return (
    <section className="panel brief">
      <div className="brief-head">
        <h2>Care-manager brief</h2>
        {result && (
          <span className="brief-meta">
            {result.cached && <span className="tag cached">cached</span>}
            <span className="muted small">
              {result.model} · {new Date(result.generated_at).toLocaleString()}
            </span>
            <button className="link" disabled={mutation.isPending} onClick={() => mutation.mutate(true)}>
              Regenerate
            </button>
          </span>
        )}
      </div>

      {!result && !mutation.isPending && (
        <>
          <p className="muted">
            Drafts a brief from de-identified facts only (age band, conditions, utilization, gaps, risk
            drivers). No name, ID or dates are sent to the model.
          </p>
          <button className="primary" onClick={() => mutation.mutate(false)}>
            Generate care brief
          </button>
        </>
      )}
      {mutation.isPending && (
        <p className="loading" aria-live="polite">
          <span className="spinner" /> Generating brief… this usually takes 10–20 seconds.
        </p>
      )}
      {mutation.error && <ErrorBox error={mutation.error} />}

      {result && !mutation.isPending && (
        <BriefBody result={result} active={active} setActive={setActive} />
      )}
    </section>
  );
}

function BriefBody({
  result,
  active,
  setActive,
}: {
  result: BriefResponse;
  active: string | null;
  setActive: (id: string | null) => void;
}) {
  const b = result.brief;
  const chip = (id: string) => (
    <button
      key={id}
      className={`fact-chip${active === id ? " active" : ""}`}
      onMouseEnter={() => setActive(id)}
      onMouseLeave={() => setActive(null)}
      onFocus={() => setActive(id)}
      onBlur={() => setActive(null)}
      onClick={() => document.getElementById(`fact-${id}`)?.scrollIntoView({ block: "nearest", behavior: "smooth" })}
    >
      {id}
    </button>
  );

  return (
    <div className="brief-grid">
      <div className="brief-main">
        <p className="draft-note">Draft for the care manager — review before contacting the patient.</p>
        <h3>Summary</h3>
        <p>{b.summary}</p>
        <h3>Why this patient is high risk</h3>
        <p>{b.risk_explanation}</p>

        <h3>Priority actions</h3>
        <ol className="actions">
          {b.priority_actions.map((a, i) => (
            <li key={i}>
              <div className="action">{a.action}</div>
              <div className="rationale">{a.rationale}</div>
              <div className="chips">{a.fact_ids.map(chip)}</div>
            </li>
          ))}
        </ol>

        <h3>
          Outreach message <span className="muted small">({b.outreach_message.split(/\s+/).length} words)</span>
        </h3>
        <blockquote className="outreach">{b.outreach_message}</blockquote>

        {b.caveats.length > 0 && (
          <>
            <h3>Caveats</h3>
            <ul className="caveats">
              {b.caveats.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </>
        )}
      </div>

      <aside className="facts">
        <h3>Facts sent to the model</h3>
        <ul>
          {result.facts.map((f) => (
            <li key={f.id} id={`fact-${f.id}`} className={active === f.id ? "highlight" : ""}>
              <span className="fact-id">{f.id}</span> {f.text}
            </li>
          ))}
        </ul>
        <p className="muted small">Prompt {result.prompt_version}</p>
      </aside>
    </div>
  );
}
