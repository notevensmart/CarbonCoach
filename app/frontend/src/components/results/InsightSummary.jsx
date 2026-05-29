import React from "react";

export default function InsightSummary({ insight }) {
  const points = Array.isArray(insight) ? insight.filter(Boolean) : [insight].filter(Boolean);

  if (!points.length) {
    return null;
  }

  return (
    <section
      aria-labelledby="estimate-summary-title"
      className="rounded-2xl border border-teal-100 bg-teal-50 p-5 shadow-sm shadow-teal-900/5"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-teal-700">
        Summary
      </p>
      <h2 id="estimate-summary-title" className="mt-1 text-xl font-semibold text-teal-950">
        What stood out
      </h2>
      <ul className="mt-3 space-y-3 text-sm leading-relaxed text-teal-950">
        {points.map((point) => (
          <li className="flex gap-3" key={point}>
            <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-700" />
            <span>{point}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
