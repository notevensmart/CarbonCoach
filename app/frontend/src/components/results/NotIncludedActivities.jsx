import React from "react";
import { CategoryIcon } from "./ActivityCard";
import { activityLabel, categoryLabel } from "./resultPresentation";

export default function NotIncludedActivities({ details }) {
  if (!details.length) {
    return null;
  }

  return (
    <section
      aria-labelledby="not-included-title"
      className="rounded-xl border border-gray-200 bg-gray-50 p-5"
    >
      <h2 id="not-included-title" className="text-lg font-semibold text-gray-900">
        Not Included in Estimated Emissions
      </h2>
      <div className="mt-3 space-y-3">
        {details.map((detail, index) => (
          <article
            key={`${detail.raw_text || detail.activity_type || index}-${index}`}
            className="rounded-lg border border-gray-100 bg-white p-4"
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
            <p className="mt-2 text-sm text-gray-600">
              This activity was recognised but is not included in estimated emissions.
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
