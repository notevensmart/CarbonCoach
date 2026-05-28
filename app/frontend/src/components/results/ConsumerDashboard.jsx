import React, { useState } from "react";
import ActivityCard from "./ActivityCard";
import ActivityCoverageSummary from "./ActivityCoverageSummary";
import CategoryCommandCenter from "./CategoryCommandCenter";
import ClarificationPriorityCard from "./ClarificationPriorityCard";
import DeveloperDetailsAccordion from "./DeveloperDetailsAccordion";
import EstimateQualityCard from "./EstimateQualityCard";
import HeroSummaryCard from "./HeroSummaryCard";
import ImpactComparisonCard from "./ImpactComparisonCard";
import InsightSummary from "./InsightSummary";
import NeedsAttention from "./NeedsAttention";
import NotIncludedActivities from "./NotIncludedActivities";
import ResultTabs from "./ResultTabs";
import { buildDashboardModel } from "./resultPresentation";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "activities", label: "Activities" },
  { id: "details", label: "Details" },
];

export default function ConsumerDashboard({ estimate }) {
  const [activeTab, setActiveTab] = useState("overview");
  const dashboard = buildDashboardModel(estimate);

  return (
    <section aria-label="Emission estimate results" className="mx-auto mt-8 max-w-7xl space-y-5">
      <ResultTabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />

      <div
        aria-labelledby="result-tab-overview"
        hidden={activeTab !== "overview"}
        id="result-panel-overview"
        role="tabpanel"
        tabIndex={0}
      >
        <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
          <HeroSummaryCard dashboard={dashboard} />
          <EstimateQualityCard quality={dashboard.quality} />
        </div>
        <div className="mt-5 grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
          <ActivityCoverageSummary coverage={dashboard.coverageSummary} />
          <InsightSummary insight={dashboard.insight} />
        </div>
        <div className="mt-5">
          <CategoryCommandCenter dashboard={dashboard} />
        </div>
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <ImpactComparisonCard comparison={dashboard.comparison} />
          <ClarificationPriorityCard clarification={dashboard.clarification} />
        </div>

        {dashboard.details.length === 0 && (
          <p className="mt-5 rounded-2xl border border-stone-200 bg-white p-5 text-sm text-stone-600 shadow-sm">
            No carbon-relevant activities were found in this entry.
          </p>
        )}
      </div>

      <div
        aria-labelledby="result-tab-activities"
        hidden={activeTab !== "activities"}
        id="result-panel-activities"
        role="tabpanel"
        tabIndex={0}
      >
        <ActivitiesView dashboard={dashboard} />
      </div>

      <div
        aria-labelledby="result-tab-details"
        hidden={activeTab !== "details"}
        id="result-panel-details"
        role="tabpanel"
        tabIndex={0}
      >
        <DeveloperDetailsAccordion
          coverageSummary={dashboard.coverageSummary}
          details={dashboard.details}
          estimate={estimate}
          comparison={estimate.comparison}
          visibleComparison={dashboard.comparison}
        />
      </div>
    </section>
  );
}

function ActivitiesView({ dashboard }) {
  return (
    <div className="space-y-5">
      {dashboard.estimatedDetails.length > 0 && (
        <section aria-labelledby="estimated-activities-title">
          <h2 id="estimated-activities-title" className="text-xl font-semibold text-stone-950">
            Estimated Activities
          </h2>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            {dashboard.estimatedDetails.map((detail, index) => (
              <ActivityCard
                detail={detail}
                key={`${detail.raw_text || detail.activity_type || index}-${index}`}
              />
            ))}
          </div>
        </section>
      )}

      <NeedsAttention details={dashboard.attentionDetails} />
      <NotIncludedActivities details={dashboard.notIncludedDetails} />

      {dashboard.details.length === 0 && (
        <p className="rounded-2xl border border-stone-200 bg-white p-5 text-sm text-stone-600 shadow-sm">
          No carbon-relevant activities were found in this entry.
        </p>
      )}
    </div>
  );
}
