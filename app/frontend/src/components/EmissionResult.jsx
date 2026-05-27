import React from "react";

const SECONDARY_STATUSES = new Set(["not_estimated", "unresolved", "failed"]);

const SOURCE_LABELS = {
  climatiq: "Climatiq",
  fallback: "Local fallback",
  unresolved: "Unresolved",
  none: "No estimate",
};

const STATUS_STYLES = {
  estimated: "bg-green-100 text-green-800",
  fallback_estimated: "bg-blue-100 text-blue-800",
  not_estimated: "bg-gray-100 text-gray-700",
  unresolved: "bg-amber-100 text-amber-800",
  failed: "bg-red-100 text-red-800",
};

export default function EmissionResult({ response }) {
  const estimate = normalizeEstimateResponse(response);

  if (estimate.version === "v1") {
    return <V1Result estimate={estimate} />;
  }

  const secondaryDetails = estimate.details.filter((detail) =>
    SECONDARY_STATUSES.has(detail.status)
  );
  const primaryDetails = estimate.details.filter(
    (detail) => !SECONDARY_STATUSES.has(detail.status)
  );

  return (
    <section
      aria-label="Emission estimate results"
      className="mt-6 rounded-md bg-white p-5 shadow-md"
    >
      <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
        V2 estimate
      </div>

      <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-gray-600">Total emissions</p>
          <p className="text-3xl font-bold text-green-700">
            {formatNumber(estimate.total.co2e)} {estimate.total.unit} CO2e
          </p>
        </div>
        {estimate.total.confidence && (
          <div className="rounded-md bg-gray-50 px-4 py-3 text-sm text-gray-700">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Total confidence
            </p>
            <p className="mt-1 font-semibold">
              {formatConfidence(estimate.total.confidence)}
            </p>
          </div>
        )}
      </div>

      <SourceBreakdown sourceBreakdown={estimate.total.source_breakdown} unit={estimate.total.unit} />

      {primaryDetails.length > 0 && (
        <DetailGroup title="Estimated activities" details={primaryDetails} />
      )}

      {secondaryDetails.length > 0 && (
        <DetailGroup
          title="Activities needing attention"
          description="These activities were kept visible but were not included as regular estimates."
          details={secondaryDetails}
        />
      )}

      {estimate.details.length === 0 && (
        <p className="mt-5 rounded-md bg-gray-50 p-4 text-sm text-gray-600">
          No carbon-relevant activities were found in this entry.
        </p>
      )}
    </section>
  );
}

function SourceBreakdown({ sourceBreakdown, unit }) {
  if (!sourceBreakdown || Object.keys(sourceBreakdown).length === 0) {
    return null;
  }

  return (
    <div className="mt-5">
      <h2 className="text-sm font-semibold text-gray-800">Source breakdown</h2>
      <dl className="mt-2 grid gap-2 sm:grid-cols-3">
        {Object.entries(sourceBreakdown).map(([source, amount]) => (
          <div key={source} className="rounded-md border border-gray-200 p-3">
            <dt className="text-xs uppercase tracking-wide text-gray-500">
              {formatKey(source)}
            </dt>
            <dd className="mt-1 font-semibold text-gray-800">
              {formatNumber(amount)} {unit}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function DetailGroup({ title, description, details }) {
  return (
    <section className="mt-6">
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      {description && <p className="mt-1 text-sm text-gray-600">{description}</p>}
      <ul className="mt-3 space-y-3">
        {details.map((detail, index) => (
          <li key={`${detail.raw_text || detail.activity_type || index}-${index}`}>
            <V2Detail detail={detail} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function V2Detail({ detail }) {
  const sourceLabel = SOURCE_LABELS[detail.source] || formatKey(detail.source);
  const statusStyle = STATUS_STYLES[detail.status] || "bg-gray-100 text-gray-700";

  return (
    <article className="rounded-md border border-gray-200 p-4 text-sm text-gray-700">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-semibold text-gray-900">{formatKey(detail.activity_type)}</h3>
          <p className="text-xs uppercase tracking-wide text-gray-500">
            {formatKey(detail.category)}
          </p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusStyle}`}>
          {formatKey(detail.status)}
        </span>
      </header>

      {detail.raw_text && <p className="mt-3 italic text-gray-600">"{detail.raw_text}"</p>}

      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
        {detail.co2e !== null && detail.co2e !== undefined && (
          <p>
            <strong>Emissions:</strong> {formatNumber(detail.co2e)} {detail.unit} CO2e
          </p>
        )}
        <p>
          <strong>Source:</strong> {sourceLabel}
        </p>
        {detail.confidence && (
          <p>
            <strong>Confidence:</strong> {formatConfidence(detail.confidence)}
          </p>
        )}
      </div>

      {detail.parameters && Object.keys(detail.parameters).length > 0 && (
        <div className="mt-4">
          <h4 className="font-semibold text-gray-800">Parameters used</h4>
          <dl className="mt-2 grid gap-x-5 gap-y-1 rounded-md bg-gray-50 p-3 sm:grid-cols-2">
            {Object.entries(detail.parameters).map(([key, value]) => (
              <div key={key} className="flex justify-between gap-3">
                <dt className="text-gray-600">{formatKey(key)}</dt>
                <dd className="text-right font-medium text-gray-900">{String(value)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {detail.factor && (
        <div className="mt-4">
          <h4 className="font-semibold text-gray-800">Factor match</h4>
          <p className="mt-1">{detail.factor.name}</p>
          <p className="mt-1 break-all font-mono text-xs text-gray-600">
            {detail.factor.activity_id}
          </p>
          <p className="mt-1">
            <strong>Score:</strong> {formatNumber(detail.factor.score)}
          </p>
          {detail.factor.match_reasons?.length > 0 && (
            <ul aria-label="Factor match reasons" className="mt-2 list-disc pl-5">
              {detail.factor.match_reasons.map((reason, index) => (
                <li key={`${reason}-${index}`}>{reason}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {detail.assumptions?.length > 0 && (
        <VisibilityList title="Assumptions" records={detail.assumptions} />
      )}

      {detail.issues?.length > 0 && (
        <VisibilityList title="Issues" records={detail.issues} warning />
      )}
    </article>
  );
}

function VisibilityList({ title, records, warning = false }) {
  return (
    <div className={`mt-4 ${warning ? "text-amber-800" : ""}`}>
      <h4 className="font-semibold">{title}</h4>
      <ul className="mt-1 list-disc pl-5">
        {records.map((record, index) => (
          <li key={`${record.code || title}-${index}`}>
            {record.code && (
              <span className="font-mono text-xs">{record.code}: </span>
            )}
            {record.message || String(record)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function V1Result({ estimate }) {
  return (
    <section
      aria-label="Emission estimate results"
      className="mt-6 rounded-md bg-white p-4 shadow-md"
    >
      <p className="text-lg">
        <strong>Estimated Emissions:</strong>{" "}
        <span className="font-bold text-green-700">
          {formatNumber(estimate.co2e)} {estimate.unit} CO2e
        </span>
      </p>
      {estimate.summary && (
        <p className="mt-2 text-sm text-gray-600">{estimate.summary}</p>
      )}
      <ul className="mt-4 space-y-3">
        {estimate.details.map((detail, index) => (
          <li key={`${detail.label || index}-${index}`} className="border-t pt-3 text-sm">
            <strong>{detail.label}</strong> ({detail.category}){" "}
            {detail.status === "ok" || detail.status === "fallback"
              ? `${formatNumber(detail.co2e)} ${detail.unit} CO2e (${detail.source})`
              : detail.error_message}
            {detail.parameters && (
              <span className="text-gray-500">
                {" "}using {formatParameters(detail.parameters)}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function normalizeEstimateResponse(data) {
  if (data.version === "v2") {
    return {
      version: "v2",
      total: {
        co2e: data.total?.co2e ?? 0,
        unit: data.total?.unit || "kg",
        confidence: data.total?.confidence,
        source_breakdown: data.total?.source_breakdown || {},
      },
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
    .map(([key, value]) => `${formatKey(key)}: ${value}`)
    .join(", ");
}

function formatKey(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatNumber(value) {
  return Number(value || 0).toFixed(2);
}
