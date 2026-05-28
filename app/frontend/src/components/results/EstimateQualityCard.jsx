import React from "react";

export default function EstimateQualityCard({ quality }) {
  if (!quality) {
    return null;
  }

  return (
    <section
      aria-labelledby="estimate-quality-title"
      className="rounded-2xl border border-stone-200 bg-stone-950 p-5 text-white shadow-sm"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-200">
        Estimate quality
      </p>
      <h2 id="estimate-quality-title" className="mt-1 text-2xl font-semibold">
        {quality.label}
      </h2>
      <div className="mt-4">
        <h3 className="text-sm font-semibold text-stone-100">Why</h3>
        <ul className="mt-2 space-y-2 text-sm text-stone-200">
          {quality.reasons.map((reason) => (
            <li className="flex gap-2" key={reason}>
              <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 rounded-full bg-amber-300" />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
