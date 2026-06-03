import React from "react";

export default function CoachingRecommendationCard({ coaching }) {
  if (!coaching?.headline && !coaching?.message) {
    return null;
  }

  const positiveFeedback = Array.isArray(coaching.positive_feedback)
    ? coaching.positive_feedback.filter(Boolean)
    : [];
  const actions = Array.isArray(coaching.actions)
    ? coaching.actions.filter((action) => action?.title || action?.reason).slice(0, 2)
    : [];

  return (
    <section
      aria-label="Coaching recommendation"
      className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm shadow-emerald-900/5"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-emerald-800">
        Coach recommendation
      </p>
      <h2 className="mt-1 text-xl font-semibold text-emerald-950">
        {coaching.headline || "A practical next step"}
      </h2>
      {coaching.message && (
        <p className="mt-3 text-sm leading-relaxed text-emerald-950">
          {coaching.message}
        </p>
      )}

      {positiveFeedback.length > 0 && (
        <div className="mt-4 border-t border-emerald-200 pt-4">
          <h3 className="text-sm font-semibold text-emerald-950">Positive signals</h3>
          <ul className="mt-2 space-y-2 text-sm text-emerald-900">
            {positiveFeedback.map((feedback) => (
              <li className="flex gap-2" key={feedback}>
                <span
                  aria-hidden="true"
                  className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-700"
                />
                <span>{feedback}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {actions.length > 0 && (
        <div className="mt-4 border-t border-emerald-200 pt-4">
          <h3 className="text-sm font-semibold text-emerald-950">Practical actions</h3>
          <ol className="mt-2 space-y-3 text-sm text-emerald-950">
            {actions.map((action, index) => (
              <li className="grid grid-cols-[1.75rem_1fr] gap-2" key={`${action.title}-${index}`}>
                <span className="flex h-6 w-6 items-center justify-center rounded-full border border-emerald-300 bg-white text-xs font-semibold text-emerald-800">
                  {index + 1}
                </span>
                <span>
                  {action.title && <strong className="block">{action.title}</strong>}
                  {action.reason && <span className="block text-emerald-900">{action.reason}</span>}
                  {action.activity_ref && (
                    <span className="mt-1 block text-xs italic text-emerald-800">
                      &quot;{action.activity_ref}&quot;
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {coaching.confidence_note && (
        <p className="mt-4 border-t border-emerald-200 pt-4 text-xs leading-relaxed text-emerald-800">
          {coaching.confidence_note}
        </p>
      )}
    </section>
  );
}
