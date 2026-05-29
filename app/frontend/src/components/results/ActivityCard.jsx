import React from "react";
import {
  activityLabel,
  categoryMeta,
  categoryLabel,
  confidenceLabel,
  confidenceTone,
  consumerAssumptionMessage,
  formatNumber,
  improvementGuidance,
  parameterSummary,
} from "./resultPresentation";

export default function ActivityCard({ detail }) {
  const assumptions = detail.assumptions || [];
  const summary = parameterSummary(detail.parameters);
  const guidance = improvementGuidance(detail);
  const confidence = confidenceLabel(detail.confidence);
  const confidenceToneMeta = confidenceTone(detail.confidence);

  return (
    <article className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm shadow-stone-900/5">
      <header className="flex items-start justify-between gap-3">
        <div className="flex gap-3">
          <CategoryIcon category={detail.category} />
          <div>
            <h3 className="font-semibold text-stone-950">{activityLabel(detail.activity_type)}</h3>
            <p className="text-sm text-stone-500">{categoryLabel(detail.category)}</p>
          </div>
        </div>
        {detail.status === "fallback_estimated" && (
          <span className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-800">
            Approximate estimate
          </span>
        )}
      </header>

      {summary && <p className="mt-4 text-sm text-stone-600">{summary}</p>}

      <div className="mt-4 flex flex-wrap items-end justify-between gap-3 border-t border-stone-100 pt-4">
        <p className="text-xl font-bold text-teal-900">
          {formatNumber(detail.co2e)} {detail.unit || "kg"} CO2e
        </p>
        {confidence && (
          <p className="text-sm text-stone-700">
            Confidence:{" "}
            <span
              className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${confidenceToneMeta.badgeClass}`}
            >
              <span className={confidenceToneMeta.textClass}>{confidence}</span>
            </span>
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

      {guidance && (
        <div className="mt-4 rounded-lg border border-teal-100 bg-teal-50 p-3 text-sm text-teal-950">
          <h4 className="font-semibold">What would improve this estimate</h4>
          <p className="mt-1">{guidance}</p>
        </div>
      )}
    </article>
  );
}

export function CategoryIcon({ category, tone = "default" }) {
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
  const meta = categoryMeta(category);
  const toneClass =
    tone === "light"
      ? "bg-white/80 text-current ring-1 ring-black/5"
      : "bg-stone-100 text-stone-900";

  return (
    <span
      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${toneClass}`}
      style={tone === "default" ? { color: meta.color } : undefined}
    >
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
