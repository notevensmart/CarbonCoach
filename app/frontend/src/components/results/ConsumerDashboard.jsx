import React from "react";
import ActivityCard from "./ActivityCard";
import CategoryBreakdown from "./CategoryBreakdown";
import DeveloperDetailsAccordion from "./DeveloperDetailsAccordion";
import HeroSummaryCard from "./HeroSummaryCard";
import InsightSummary from "./InsightSummary";
import NeedsAttention from "./NeedsAttention";
import NotIncludedActivities from "./NotIncludedActivities";
import { buildDashboardModel } from "./resultPresentation";

export default function ConsumerDashboard({ estimate }) {
  const dashboard = buildDashboardModel(estimate);

  return (
    <section aria-label="Emission estimate results" className="mt-6 space-y-5">
      <HeroSummaryCard dashboard={dashboard} />
      <InsightSummary insight={dashboard.insight} />
      <CategoryBreakdown dashboard={dashboard} />

      {dashboard.estimatedDetails.length > 0 && (
        <section aria-labelledby="estimated-activities-title">
          <h2 id="estimated-activities-title" className="text-xl font-semibold text-gray-900">
            Estimated Activities
          </h2>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            {dashboard.estimatedDetails.map((detail, index) => (
              <ActivityCard
                key={`${detail.raw_text || detail.activity_type || index}-${index}`}
                detail={detail}
              />
            ))}
          </div>
        </section>
      )}

      <NeedsAttention details={dashboard.attentionDetails} />
      <NotIncludedActivities details={dashboard.notIncludedDetails} />

      {dashboard.details.length === 0 && (
        <p className="rounded-xl border border-gray-200 bg-white p-4 text-sm text-gray-600 shadow-sm">
          No carbon-relevant activities were found in this entry.
        </p>
      )}

      <DeveloperDetailsAccordion estimate={estimate} details={dashboard.details} />
    </section>
  );
}
