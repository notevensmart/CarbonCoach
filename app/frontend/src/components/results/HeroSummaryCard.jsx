import React from "react";
import { confidenceLabel, formatNumber } from "./resultPresentation";

export default function HeroSummaryCard({ dashboard }) {
  const attentionCount = dashboard.attentionDetails.length;
  const confidence = confidenceLabel(dashboard.confidence);

  return (
    <section
      aria-labelledby="footprint-title"
      className="overflow-hidden rounded-3xl bg-teal-950 p-6 text-white shadow-lg shadow-teal-950/15"
    >
      <p className="text-xs font-semibold uppercase tracking-widest text-teal-100">
        Daily reflection
      </p>
      <h2 id="footprint-title" className="mt-2 text-xl font-semibold">
        Today&apos;s Estimated Footprint
      </h2>

      {dashboard.total > 0 ? (
        <p className="mt-3 text-4xl font-bold tracking-tight">
          {formatNumber(dashboard.total)} {dashboard.unit} CO2e
        </p>
      ) : (
        <p className="mt-4 text-lg font-medium text-teal-50">
          No emissions estimate is available yet.
        </p>
      )}

      <dl className="mt-5 flex flex-wrap gap-x-8 gap-y-3 text-sm">
        {dashboard.mainDriver && (
          <div>
            <dt className="text-teal-200">Main driver</dt>
            <dd className="font-semibold">{dashboard.mainDriver}</dd>
          </div>
        )}
        {confidence && (
          <div>
            <dt className="text-teal-200">Confidence</dt>
            <dd className="font-semibold">{confidence}</dd>
          </div>
        )}
      </dl>

      {attentionCount > 0 && (
        <p className="mt-5 rounded-lg bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900">
          {attentionCount} {attentionCount === 1 ? "activity" : "activities"} could not yet be
          included.
        </p>
      )}
    </section>
  );
}
