import React from "react";

export default function ImpactComparisonCard({ comparison }) {
  if (!comparison?.message) {
    return null;
  }

  return (
    <section
      aria-label="Impact comparison"
      className="rounded-xl border border-teal-100 bg-teal-50 p-4 shadow-sm"
    >
      <h2 className="text-sm font-semibold uppercase tracking-wide text-teal-800">In Context</h2>
      <p className="mt-2 text-base text-teal-950">{comparison.message}</p>
    </section>
  );
}
