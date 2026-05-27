import React from "react";
import { CategoryIcon } from "./ActivityCard";
import { activityLabel, categoryLabel } from "./resultPresentation";

const FRIENDLY_COPY = {
  unresolved: "We could not estimate this activity yet.",
  failed: "This activity could not be estimated right now.",
};

export default function NeedsAttention({ details }) {
  if (!details.length) {
    return null;
  }

  return (
    <section
      aria-labelledby="needs-attention-title"
      className="rounded-xl border border-amber-200 bg-amber-50 p-5"
    >
      <h2 id="needs-attention-title" className="text-xl font-semibold text-gray-900">
        Needs Attention
      </h2>
      <div className="mt-3 space-y-3">
        {details.map((detail, index) => (
          <article
            key={`${detail.raw_text || detail.activity_type || index}-${index}`}
            className="rounded-lg bg-white p-4"
          >
            <div className="flex gap-3">
              <CategoryIcon category={detail.category} />
              <div>
                <h3 className="font-semibold text-gray-900">{activityLabel(detail.activity_type)}</h3>
                <p className="text-sm text-gray-500">{categoryLabel(detail.category)}</p>
              </div>
            </div>
            {detail.raw_text && (
              <p className="mt-3 text-sm italic text-gray-600">&quot;{detail.raw_text}&quot;</p>
            )}
            <p className="mt-2 text-sm text-gray-800">
              {FRIENDLY_COPY[detail.status]}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
