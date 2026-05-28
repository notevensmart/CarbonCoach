import React from "react";

const COVERAGE_ITEMS = [
  { key: "found", label: "activities found" },
  { key: "estimated", label: "estimated" },
  { key: "needDetails", label: "need details" },
  { key: "notIncluded", label: "not included yet" },
];

export default function ActivityCoverageSummary({ coverage }) {
  if (!coverage) {
    return null;
  }

  return (
    <section
      aria-labelledby="activity-coverage-title"
      className="rounded-2xl border border-teal-100 bg-white p-5 shadow-sm shadow-teal-900/5"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-teal-700">
            Activity coverage
          </p>
          <h2 id="activity-coverage-title" className="mt-1 text-xl font-semibold text-stone-950">
            We found {coverage.found} {coverage.found === 1 ? "activity" : "activities"}
          </h2>
        </div>
        {coverage.fromBackend && (
          <span className="w-fit rounded-full border border-teal-100 bg-teal-50 px-3 py-1 text-xs font-semibold text-teal-800">
            Backend coverage
          </span>
        )}
      </div>

      <dl className="mt-5 grid gap-3 sm:grid-cols-4">
        {COVERAGE_ITEMS.slice(1).map((item) => (
          <div key={item.key} className="rounded-xl border border-stone-200 bg-stone-50 p-3">
            <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500">
              {item.label}
            </dt>
            <dd className="mt-1 text-2xl font-semibold text-stone-950">{coverage[item.key]}</dd>
          </div>
        ))}
        {coverage.notRepresented !== null && coverage.notRepresented !== undefined && (
          <div className="rounded-xl border border-stone-200 bg-stone-50 p-3">
            <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500">
              not represented yet
            </dt>
            <dd className="mt-1 text-2xl font-semibold text-stone-950">
              {coverage.notRepresented}
            </dd>
          </div>
        )}
      </dl>

      {coverage.partial && (
        <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-950">
          This is a partial estimated footprint because at least one represented activity needs
          more detail.
        </p>
      )}
    </section>
  );
}
