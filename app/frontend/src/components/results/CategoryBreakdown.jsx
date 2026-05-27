import React from "react";
import { formatNumber } from "./resultPresentation";

export default function CategoryBreakdown({ dashboard }) {
  let left = 0;
  const accessibleSummary = dashboard.breakdown
    .map(
      (category) =>
        `${category.label} ${formatNumber(category.amount)} ${dashboard.unit} CO2e, ${category.percentage} percent`
    )
    .join("; ");

  return (
    <section
      aria-labelledby="category-breakdown-title"
      className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
    >
      <h2 id="category-breakdown-title" className="text-xl font-semibold text-gray-900">
        Breakdown of estimated emissions
      </h2>

      {dashboard.breakdown.length === 0 ? (
        <p className="mt-3 text-sm text-gray-600">No estimated emissions to break down yet.</p>
      ) : (
        <>
          <svg
            aria-label={`Breakdown of estimated emissions: ${accessibleSummary}`}
            className="mt-5 h-7 w-full"
            role="img"
            viewBox="0 0 100 12"
            preserveAspectRatio="none"
          >
            {dashboard.breakdown.map((category) => {
              const width = (category.amount / dashboard.total) * 100;
              const segment = (
                <rect
                  key={category.key}
                  x={left}
                  y="0"
                  width={width}
                  height="12"
                  fill={category.color}
                />
              );
              left += width;
              return segment;
            })}
          </svg>
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {dashboard.breakdown.map((category) => (
              <li key={category.key} className="flex items-center justify-between gap-4 text-sm">
                <span className="flex items-center gap-2 text-gray-700">
                  <span
                    aria-hidden="true"
                    className="inline-block h-3 w-3 rounded-full"
                    style={{ backgroundColor: category.color }}
                  />
                  {category.label}
                </span>
                <span className="font-semibold text-gray-900">
                  {formatNumber(category.amount)} {dashboard.unit} CO2e ({category.percentage}%)
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      {dashboard.attentionDetails.length > 0 && (
        <p className="mt-4 rounded-md bg-amber-50 p-3 text-sm text-amber-900">
          Activities needing attention are not included in this breakdown.
        </p>
      )}
    </section>
  );
}
