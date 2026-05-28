import React from "react";
import { CategoryIcon } from "./ActivityCard";
import { formatNumber } from "./resultPresentation";

export default function CategoryCommandCenter({ dashboard }) {
  let left = 0;
  const accessibleSummary = dashboard.breakdown
    .map(
      (category) =>
        `${category.label} ${formatNumber(category.amount)} ${dashboard.unit} CO2e, ${category.percentage} percent`
    )
    .join("; ");

  return (
    <section
      aria-labelledby="category-command-title"
      className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-teal-700">
            Category command center
          </p>
          <h2 id="category-command-title" className="mt-1 text-xl font-semibold text-stone-950">
            Breakdown of estimated emissions
          </h2>
        </div>
        {dashboard.total > 0 && (
          <p className="text-sm text-stone-600">
            {formatNumber(dashboard.total)} {dashboard.unit} CO2e included
          </p>
        )}
      </div>

      {dashboard.breakdown.length > 0 && (
        <svg
          aria-label={`Breakdown of estimated emissions: ${accessibleSummary}`}
          className="mt-5 h-8 w-full overflow-hidden rounded-full bg-stone-100"
          role="img"
          viewBox="0 0 100 12"
          preserveAspectRatio="none"
        >
          {dashboard.breakdown.map((category) => {
            const width = (category.amount / dashboard.total) * 100;
            const segment = (
              <rect
                fill={category.color}
                height="12"
                key={category.key}
                width={width}
                x={left}
                y="0"
              />
            );
            left += width;
            return segment;
          })}
        </svg>
      )}

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {dashboard.categoryCommand.map((category) => (
          <article
            className={`rounded-2xl border p-4 ${category.softClass}`}
            key={category.key}
          >
            <div
              aria-hidden="true"
              aria-label={`${category.label} category color`}
              className="mb-4 h-2 rounded-full"
              data-category-color={category.key}
              style={{ backgroundColor: category.color }}
            />
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="flex items-center gap-2 font-semibold">
                  <span
                    aria-hidden="true"
                    className="inline-block h-3 w-3 rounded-full"
                    style={{ backgroundColor: category.color }}
                  />
                  {category.label}
                </h3>
                <p className="mt-1 text-2xl font-semibold">
                  {formatNumber(category.amount)} {dashboard.unit}
                </p>
                <p className="text-sm">
                  {dashboard.total > 0 ? `${category.percentage}% of estimated total` : "No included emissions"}
                </p>
              </div>
              <CategoryIcon category={category.key} tone="light" />
            </div>

            <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
              <div className="rounded-xl bg-white/70 p-3">
                <dt className="text-xs font-semibold uppercase tracking-wide opacity-70">
                  Estimated
                </dt>
                <dd className="mt-1 font-semibold">{category.estimatedCount}</dd>
              </div>
              <div className="rounded-xl bg-white/70 p-3">
                <dt className="text-xs font-semibold uppercase tracking-wide opacity-70">
                  Need details
                </dt>
                <dd className="mt-1 font-semibold">{category.attentionCount}</dd>
              </div>
            </dl>

            {category.representedCount === 0 && (
              <p className="mt-3 text-sm font-medium opacity-75">No represented activity.</p>
            )}
          </article>
        ))}
      </div>

      {dashboard.total <= 0 && (
        <p className="mt-4 rounded-xl border border-stone-200 bg-stone-50 p-3 text-sm text-stone-700">
          No estimated emissions to break down yet.
        </p>
      )}
    </section>
  );
}
