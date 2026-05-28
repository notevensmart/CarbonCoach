import React from "react";

export default function InsightSummary({ insight }) {
  if (!insight) {
    return null;
  }

  return (
    <section
      aria-labelledby="reflection-summary-title"
      className="rounded-2xl border border-teal-100 bg-teal-50 p-5"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-teal-700">
        Deterministic reflection
      </p>
      <h2 id="reflection-summary-title" className="mt-1 text-xl font-semibold text-teal-950">
        What CarbonCoach understood
      </h2>
      <p className="mt-3 text-sm leading-relaxed text-teal-950">{insight}</p>
    </section>
  );
}
