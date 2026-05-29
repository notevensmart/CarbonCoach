import React from "react";
import { confidenceTone } from "./resultPresentation";

export default function EstimateQualityCard({ quality }) {
  if (!quality) {
    return null;
  }

  const tone = confidenceTone(quality.level);

  return (
    <section
      aria-labelledby="estimate-quality-title"
      className={`rounded-2xl border p-5 shadow-sm ${tone.cardClass}`}
    >
      <p className="text-xs font-semibold uppercase tracking-wide opacity-75">
        Estimate quality
      </p>
      <h2 id="estimate-quality-title" className="mt-1 flex items-center gap-2 text-2xl font-semibold">
        <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${tone.dotClass}`} />
        <span>{quality.label}</span>
      </h2>
      <div className="mt-4">
        <h3 className="text-sm font-semibold">Why</h3>
        <ul className="mt-2 space-y-2 text-sm">
          {quality.reasons.map((reason) => (
            <li className="flex gap-2" key={reason}>
              <span aria-hidden="true" className={`mt-2 h-1.5 w-1.5 rounded-full ${tone.dotClass}`} />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
