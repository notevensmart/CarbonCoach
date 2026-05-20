import { useMemo, useState } from "react";

const API_URL = process.env.REACT_APP_API_URL || "";

const sampleEntry =
  "Took a 10 km bus ride, had a vegetarian lunch, used 4 kWh of electricity, and threw away 1 kg of food waste.";

function formatKg(value) {
  const number = Number(value || 0);
  return `${number.toFixed(number >= 10 ? 1 : 2)} kg CO2e`;
}

function App() {
  const [journal, setJournal] = useState(sampleEntry);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const apiMode = useMemo(() => {
    if (!result) return "Ready";
    return result.used_api ? "Climatiq API" : "Local fallback";
  }, [result]);

  async function estimate() {
    const entry = journal.trim();
    if (!entry) {
      setError("Add a journal entry first.");
      setResult(null);
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_URL}/api/estimate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ journal: entry }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "The estimate could not be calculated.");
      }

      setResult(payload);
    } catch (err) {
      setResult(null);
      setError(err.message || "The estimate could not be calculated.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Journal emissions estimator</p>
            <h1>CarbonCoach</h1>
          </div>
          <div className="status-pill">{apiMode}</div>
        </header>

        <div className="input-grid">
          <section className="entry-panel" aria-labelledby="journal-label">
            <div className="panel-heading">
              <label id="journal-label" htmlFor="journal-entry">
                Journal entry
              </label>
              <span>{journal.trim().length} chars</span>
            </div>
            <textarea
              id="journal-entry"
              value={journal}
              onChange={(event) => setJournal(event.target.value)}
              placeholder="Took a 5 km bus ride and cooked dinner at home."
            />
            <div className="actions">
              <button type="button" className="secondary-button" onClick={() => setJournal(sampleEntry)}>
                Load sample
              </button>
              <button type="button" className="primary-button" onClick={estimate} disabled={loading}>
                {loading ? "Estimating..." : "Estimate"}
              </button>
            </div>
            {error && <div className="error-message">{error}</div>}
          </section>

          <section className="summary-panel" aria-live="polite">
            <p className="eyebrow">Estimated total</p>
            <div className="total-value">{result ? formatKg(result.co2e) : "--"}</div>
            <div className="summary-meta">
              <span>{result?.activities?.length || 0} activities</span>
              <span>{result?.data_version || "No run yet"}</span>
            </div>
            {result?.errors?.length > 0 && (
              <div className="warning-box">
                {result.errors.slice(0, 2).map((item) => (
                  <p key={item}>{item}</p>
                ))}
              </div>
            )}
          </section>
        </div>

        <section className="activity-section">
          <div className="section-heading">
            <h2>Detected activities</h2>
            <span>{result ? result.unit : "kg CO2e"}</span>
          </div>

          {result?.activities?.length ? (
            <div className="activity-table" role="table" aria-label="Detected activities">
              <div className="table-row table-head" role="row">
                <span role="columnheader">Activity</span>
                <span role="columnheader">Matched factor</span>
                <span role="columnheader">Input</span>
                <span role="columnheader">Estimate</span>
              </div>
              {result.activities.map((activity) => (
                <div className="table-row" role="row" key={`${activity.activity_id}-${activity.label}`}>
                  <div role="cell">
                    <strong>{activity.label}</strong>
                    <small>{activity.kind}</small>
                  </div>
                  <div role="cell">
                    <span>{activity.factor_name}</span>
                    <small>{activity.source}</small>
                  </div>
                  <div role="cell">
                    <span>{describeParameters(activity.parameters)}</span>
                    <small>{activity.unit_type}</small>
                  </div>
                  <div role="cell">
                    <strong>{formatKg(activity.co2e)}</strong>
                    <small>{activity.method}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">No estimate has been run yet.</div>
          )}
        </section>
      </section>
    </main>
  );
}

function describeParameters(parameters = {}) {
  if (parameters.distance) {
    const passengerText = parameters.passengers ? `${parameters.passengers} passenger, ` : "";
    return `${passengerText}${parameters.distance} ${parameters.distance_unit || "km"}`;
  }
  if (parameters.energy) return `${parameters.energy} ${parameters.energy_unit || "kWh"}`;
  if (parameters.weight) return `${parameters.weight} ${parameters.weight_unit || "kg"}`;
  if (parameters.money) return `${parameters.money} ${(parameters.money_unit || "aud").toUpperCase()}`;
  if (parameters.number) return `${parameters.number}`;
  return "Default quantity";
}

export default App;
