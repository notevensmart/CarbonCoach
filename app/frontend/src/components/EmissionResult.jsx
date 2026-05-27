import React from "react";
import ConsumerDashboard from "./results/ConsumerDashboard";

export default function EmissionResult({ response }) {
  const estimate = normalizeEstimateResponse(response);

  if (estimate.version === "v2") {
    return <ConsumerDashboard estimate={estimate} />;
  }

  return <V1Result estimate={estimate} />;
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

function formatParameters(parameters) {
  return Object.entries(parameters)
    .map(([key, value]) => `${formatLabel(key)}: ${value}`)
    .join(", ");
}

function formatLabel(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatNumber(value) {
  return Number(value || 0).toFixed(2);
}
