import React from "react";

export default function ImpactComparisonCard({ comparison }) {
  if (!comparison?.message) {
    return null;
  }

  return (
    <section
      aria-label="Impact comparison"
      className="rounded-2xl border border-blue-100 bg-blue-50 p-5 shadow-sm"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wide text-blue-800">In Context</h2>
      <p className="mt-2 text-base text-blue-950">{comparison.message}</p>
    </section>
  );
}
