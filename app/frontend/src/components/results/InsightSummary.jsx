import React from "react";

export default function InsightSummary({ insight }) {
  if (!insight) {
    return null;
  }

  return (
    <section aria-label="Insight summary" className="rounded-xl border border-green-100 bg-green-50 p-4">
      <p className="text-sm leading-relaxed text-green-950">{insight}</p>
    </section>
  );
}
