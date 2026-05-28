import React from "react";
import { CategoryIcon } from "./ActivityCard";
import { activityLabel, categoryLabel, friendlyStatusCopy } from "./resultPresentation";

export default function NotIncludedActivities({ details }) {
  if (!details.length) {
    return null;
  }

  return (
    <section
      aria-labelledby="not-included-title"
      className="rounded-2xl border border-stone-200 bg-stone-50 p-5"
    >
      <h2 id="not-included-title" className="text-lg font-semibold text-stone-950">
        Not Included in Estimated Emissions
      </h2>
      <div className="mt-3 space-y-3">
        {details.map((detail, index) => (
          <article
            key={`${detail.raw_text || detail.activity_type || index}-${index}`}
            className="rounded-xl border border-stone-100 bg-white p-4"
          >
            <div className="flex gap-3">
              <CategoryIcon category={detail.category} />
              <div>
                <h3 className="font-semibold text-stone-950">{activityLabel(detail.activity_type)}</h3>
                <p className="text-sm text-stone-500">{categoryLabel(detail.category)}</p>
              </div>
            </div>
            {detail.raw_text && (
              <p className="mt-3 text-sm italic text-stone-600">&quot;{detail.raw_text}&quot;</p>
            )}
            <p className="mt-2 text-sm text-stone-600">
              {friendlyStatusCopy(detail.status)}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
