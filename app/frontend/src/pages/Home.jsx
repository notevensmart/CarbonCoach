import React, { useState } from "react";

const DEFAULT_ENDPOINT = "/api/estimate-v2";

const Home = () => {
  const [entry, setEntry] = useState("");
  const [emissions, setEmissions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    setLoading(true);
    setError("");

    try {
      const apiBaseUrl = process.env.REACT_APP_API_BASE_URL || "";
      const endpoint = process.env.REACT_APP_ESTIMATE_ENDPOINT || DEFAULT_ENDPOINT;
      const res = await fetch(`${apiBaseUrl}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ journal: entry }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Server error");
      }

      setEmissions(normalizeEstimateResponse(data));
    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to estimate emissions. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <h1 className="mb-6 text-4xl font-bold text-green-700">
        CarbonCoach
      </h1>

      <div className="mb-4">
        <h2 className="text-xl font-semibold">What did you do today?</h2>
      </div>

      <textarea
        className="mb-4 h-32 w-full rounded-md border p-4 shadow-sm"
        placeholder="e.g., Used a 2 kW heater for 3 hours..."
        value={entry}
        onChange={(event) => setEntry(event.target.value)}
      />

      <button
        onClick={handleSubmit}
        disabled={loading}
        className="rounded bg-green-600 px-4 py-2 font-semibold text-white hover:bg-green-700 disabled:cursor-not-allowed disabled:bg-gray-400"
      >
        {loading ? "Estimating..." : "Estimate Emissions"}
      </button>

      {emissions && (
        <section className="mt-6 rounded-md bg-white p-4 shadow-md">
          <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Response version: {emissions.version.toUpperCase()}
          </div>

          <p className="text-lg">
            <strong>Estimated Emissions:</strong>{" "}
            <span className="font-bold text-green-700">
              {formatNumber(emissions.co2e)} {emissions.unit} CO2e
            </span>
          </p>

          {emissions.total?.confidence && (
            <p className="mt-2 text-sm text-gray-700">
              <strong>Confidence:</strong>{" "}
              {formatConfidence(emissions.total.confidence)}
            </p>
          )}

          {emissions.summary && (
            <p className="mt-2 text-sm text-gray-600">{emissions.summary}</p>
          )}

          {emissions.total?.source_breakdown && (
            <div className="mt-3 text-sm text-gray-700">
              <strong>Source breakdown:</strong>{" "}
              {formatSourceBreakdown(emissions.total.source_breakdown)}
            </div>
          )}

          <ul className="mt-4 space-y-3">
            {emissions.details.map((detail, index) => (
              <li key={`${detail.raw_text || detail.label || index}-${index}`} className="border-t pt-3">
                <EstimateDetail detail={detail} version={emissions.version} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {error && (
        <div className="mt-4 font-semibold text-red-600">{error}</div>
      )}
    </div>
  );
};

function EstimateDetail({ detail, version }) {
  if (version === "v2") {
    return (
      <div className="text-sm text-gray-700">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <strong>{detail.activity_type}</strong>
          <span>({detail.category})</span>
          <span className="text-xs font-semibold text-gray-700">
            status: {detail.status}
          </span>
        </div>

        <p className="mt-1 text-gray-600">{detail.raw_text}</p>

        {detail.co2e !== null && detail.co2e !== undefined && (
          <p className="mt-2">
            {formatNumber(detail.co2e)} {detail.unit} CO2e
            {detail.source && detail.source !== "none" ? ` (${detail.source})` : ""}
          </p>
        )}

        {detail.confidence && (
          <p className="mt-1">
            <strong>Confidence:</strong> {formatConfidence(detail.confidence)}
          </p>
        )}

        {detail.parameters && Object.keys(detail.parameters).length > 0 && (
          <p className="mt-1">
            <strong>Parameters:</strong> {formatParameters(detail.parameters)}
          </p>
        )}

        {detail.factor && (
          <div className="mt-2">
            <strong>Climatiq factor:</strong> {detail.factor.name}
            <p className="mt-1 break-all font-mono text-xs text-gray-600">
              {detail.factor.activity_id}
            </p>
            <p className="mt-1">
              <strong>Factor match score:</strong> {formatNumber(detail.factor.score)}
            </p>
            {detail.factor.match_reasons?.length > 0 && (
              <ul className="mt-1 list-disc pl-5">
                {detail.factor.match_reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {detail.assumptions?.length > 0 && (
          <div className="mt-2">
            <strong>Assumptions:</strong>
            <ul className="mt-1 list-disc pl-5">
              {detail.assumptions.map((assumption) => (
                <li key={assumption.code}>
                  <span className="font-mono text-xs">{assumption.code}</span>:{" "}
                  {assumption.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        {detail.issues?.length > 0 && (
          <div className="mt-2 text-amber-700">
            <strong>Issues:</strong>
            <ul className="mt-1 list-disc pl-5">
              {detail.issues.map((issue) => (
                <li key={issue.code}>
                  <span className="font-mono text-xs">{issue.code}</span>:{" "}
                  {issue.message}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="text-sm text-gray-700">
      <strong>{detail.label}</strong> ({detail.category}){" "}
      {detail.status === "ok" || detail.status === "fallback"
        ? `${formatNumber(detail.co2e)} ${detail.unit} CO2e (${detail.source})`
        : detail.error_message}
      {detail.parameters && (
        <span className="text-gray-500">
          {" "}using {formatParameters(detail.parameters)}
        </span>
      )}
    </div>
  );
}

function normalizeEstimateResponse(data) {
  if (data.version === "v2") {
    return {
      version: "v2",
      co2e: data.total?.co2e ?? 0,
      unit: data.total?.unit || "kg",
      summary: `Total emissions: ${formatNumber(data.total?.co2e ?? 0)} ${data.total?.unit || "kg"} CO2e`,
      total: data.total,
      details: data.details || [],
    };
  }

  return {
    version: "v1",
    co2e: data.result?.co2e ?? 0,
    unit: data.result?.unit || "kg",
    summary: data.result?.summary,
    details: data.result?.details || [],
  };
}

function formatConfidence(confidence) {
  const level = confidence.level
    ? confidence.level.charAt(0).toUpperCase() + confidence.level.slice(1)
    : "Unknown";
  return `${level} (${formatNumber(confidence.score)})`;
}

function formatParameters(parameters) {
  return Object.entries(parameters)
    .map(([key, value]) => `${key}: ${value}`)
    .join(", ");
}

function formatSourceBreakdown(sourceBreakdown) {
  return Object.entries(sourceBreakdown)
    .map(([key, value]) => `${key}: ${formatNumber(value)}`)
    .join(", ");
}

function formatNumber(value) {
  return Number(value || 0).toFixed(2);
}

export default Home;
