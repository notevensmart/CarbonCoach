import React from "react";
import {
  activityLabel,
  categoryLabel,
  confidenceLabel,
  consumerAssumptionMessage,
  formatNumber,
  parameterSummary,
} from "./resultPresentation";

export default function ActivityCard({ detail }) {
  const assumptions = detail.assumptions || [];
  const summary = parameterSummary(detail.parameters);

  return (
    <article className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <header className="flex items-start justify-between gap-3">
        <div className="flex gap-3">
          <CategoryIcon category={detail.category} />
          <div>
            <h3 className="font-semibold text-gray-900">{activityLabel(detail.activity_type)}</h3>
            <p className="text-sm text-gray-500">{categoryLabel(detail.category)}</p>
          </div>
        </div>
        {detail.status === "fallback_estimated" && (
          <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-800">
            Approximate estimate
          </span>
        )}
      </header>

      {summary && <p className="mt-4 text-sm text-gray-600">{summary}</p>}

      <div className="mt-4 flex flex-wrap items-end justify-between gap-3 border-t border-gray-100 pt-4">
        <p className="text-xl font-bold text-green-800">
          {formatNumber(detail.co2e)} {detail.unit || "kg"} CO2e
        </p>
        {detail.confidence && (
          <p className="text-sm text-gray-700">
            Confidence: <span className="font-semibold">{confidenceLabel(detail.confidence)}</span>
          </p>
        )}
      </div>

      {assumptions.length > 0 && (
        <div className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-950">
          <h4 className="font-semibold">What we assumed</h4>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {assumptions.map((assumption, index) => (
              <li key={`${assumption.code || "assumption"}-${index}`}>
                {consumerAssumptionMessage(assumption)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

export function CategoryIcon({ category }) {
  const paths = {
    transport: (
      <>
        <path d="M4 15h16l-2-6H6l-2 6Z" />
        <path d="M7 15v2M17 15v2M8 9l2-3h4l2 3" />
      </>
    ),
    energy: <path d="M13 2 5 13h6l-1 9 9-12h-6V2Z" />,
    goods_services: (
      <>
        <path d="M5 8h14v12H5z" />
        <path d="M9 8a3 3 0 0 1 6 0" />
      </>
    ),
    waste: (
      <>
        <path d="M7 7h10l-1 14H8L7 7Z" />
        <path d="M5 7h14M10 4h4" />
      </>
    ),
  };

  return (
    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-green-50 text-green-800">
      <svg
        aria-hidden="true"
        className="h-5 w-5"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
        viewBox="0 0 24 24"
      >
        {paths[category] || paths.goods_services}
      </svg>
    </span>
  );
}
