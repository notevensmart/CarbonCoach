export const INCLUDED_STATUSES = new Set(["estimated", "fallback_estimated"]);
export const ATTENTION_STATUSES = new Set(["unresolved", "failed"]);

export const CATEGORIES = [
  {
    key: "transport",
    label: "Transport",
    color: "#0072b2",
    softClass: "bg-sky-50 text-sky-950 border-sky-200",
  },
  {
    key: "energy",
    label: "Energy",
    color: "#e69f00",
    softClass: "bg-amber-50 text-amber-950 border-amber-200",
  },
  {
    key: "goods_services",
    label: "Goods",
    color: "#cc79a7",
    softClass: "bg-fuchsia-50 text-fuchsia-950 border-fuchsia-200",
  },
  {
    key: "waste",
    label: "Waste",
    color: "#009e73",
    softClass: "bg-emerald-50 text-emerald-950 border-emerald-200",
  },
];

const CATEGORY_LABELS = Object.fromEntries(
  CATEGORIES.map((category) => [category.key, category.label])
);

const COMBINED_PARAMETER_KEYS = [
  ["distance", "distance_unit"],
  ["energy", "energy_unit"],
  ["duration", "duration_unit"],
  ["power", "power_unit"],
  ["weight", "weight_unit"],
  ["money", "money_unit"],
  ["number", "number_unit"],
];

const INTERNAL_PARAMETER_KEYS = new Set([
  "emissions_boundary",
  "factor_specificity",
  "fallback_factor_key",
  "calculation_boundary",
  "origin_place_id",
  "destination_place_id",
  "origin_place_name",
  "destination_place_name",
  "origin_place_type",
  "destination_place_type",
  "origin_region",
  "destination_region",
  "origin_matched_alias",
  "destination_matched_alias",
  "origin_match_type",
  "destination_match_type",
  "origin_confidence",
  "destination_confidence",
  "distance_confidence",
  "distance_source",
  "route_exact",
  "route_source_version",
  "route_path_place_ids",
  "route_path_place_names",
  "origin_route_node_id",
  "destination_route_node_id",
  "route_path_node_ids",
  "route_path_edge_ids",
  "snap_confidence",
  "snap_source",
  "origin_snap_distance_m",
  "destination_snap_distance_m",
  "origin_snap_confidence",
  "destination_snap_confidence",
  "origin_snap_source",
  "destination_snap_source",
  "region_name",
  "factor_region",
  "fallback_region",
  "region_source",
  "region_source_version",
  "region_confidence",
]);

const AU_DAILY_REFERENCE = {
  kgCo2ePerDay: 44,
  label: "broad Australian per-person daily emissions reference",
};

export function buildDashboardModel(estimate) {
  const details = Array.isArray(estimate.details) ? estimate.details : [];
  const estimatedDetails = details.filter((detail) =>
    INCLUDED_STATUSES.has(detail.status)
  );
  const attentionDetails = details.filter((detail) =>
    ATTENTION_STATUSES.has(detail.status)
  );
  const notIncludedDetails = details.filter(
    (detail) => detail.status === "not_estimated"
  );

  const categoryCommand = CATEGORIES.map((category) => {
    const categoryDetails = details.filter((detail) => detail.category === category.key);
    const categoryEstimated = categoryDetails.filter((detail) =>
      INCLUDED_STATUSES.has(detail.status)
    );
    const amount = categoryEstimated.reduce((sum, detail) => sum + includedAmount(detail), 0);
    return {
      ...category,
      amount,
      estimatedCount: categoryEstimated.length,
      attentionCount: categoryDetails.filter((detail) => ATTENTION_STATUSES.has(detail.status))
        .length,
      notIncludedCount: categoryDetails.filter((detail) => detail.status === "not_estimated")
        .length,
      representedCount: categoryDetails.length,
    };
  });

  const contributingTotal = categoryCommand.reduce(
    (sum, category) => sum + category.amount,
    0
  );
  const categories = categoryCommand.filter((category) => category.amount > 0);

  const positiveLargest = categories.length
    ? Math.max(...categories.map((category) => category.amount))
    : 0;
  const largestCategories = categories.filter(
    (category) => Math.abs(category.amount - positiveLargest) < 1e-9
  );
  const mainDriver =
    largestCategories.length === 1
      ? largestCategories[0].label
      : largestCategories.length > 1
        ? "Multiple categories"
        : null;

  const breakdown = categories.map((category) => ({
    ...category,
    percentage: percentage(category.amount, contributingTotal),
  }));
  const categoryCommandWithPercentages = categoryCommand.map((category) => ({
    ...category,
    percentage: percentage(category.amount, contributingTotal),
  }));
  const coverageSummary = buildCoverageSummary(estimate.coverage, details);
  const assumptionActivityCount = details.filter((detail) => detail.assumptions?.length > 0)
    .length;
  const assumptionCount = details.reduce(
    (total, detail) => total + (detail.assumptions?.length || 0),
    0
  );
  const fallbackCount = estimatedDetails.filter(
    (detail) => detail.status === "fallback_estimated" || detail.source === "fallback"
  ).length;
  const topActivity = topEstimatedActivity(estimatedDetails);
  const largestCategoryLabels = categories
    .filter((category) => Math.abs(category.amount - positiveLargest) < 1e-9)
    .map((category) => category.label);
  const clarification = buildClarificationPriority(
    estimate.clarification_suggestions,
    attentionDetails
  );

  return {
    total: contributingTotal,
    unit: estimate.total?.unit || "kg",
    confidence: estimate.total?.confidence,
    estimatedDetails,
    attentionDetails,
    notIncludedDetails,
    details,
    breakdown,
    categoryCommand: categoryCommandWithPercentages,
    coverageSummary,
    quality: buildQuality({
      confidence: estimate.total?.confidence,
      coverageSummary,
      assumptionActivityCount,
      assumptionCount,
      fallbackCount,
      largestCategoryLabels,
    }),
    mainDriver,
    topActivity,
    clarification,
    comparison: displayableComparison(
      estimate.comparison,
      contributingTotal,
      estimate.total?.confidence,
      estimate.coverage
    ),
    coaching: estimate.coaching || null,
    insight: buildInsight({
      breakdown,
      contributingTotal,
      confidence: estimate.total?.confidence,
      estimatedDetails,
      attentionDetails,
      topActivity,
      coverageSummary,
      assumptionCount,
      fallbackCount,
      clarification,
    }),
  };
}

export function displayableComparison(comparison, total, confidence, coverage) {
  if (
    !comparison?.message ||
    comparison.approximate !== true ||
    total <= 0 ||
    !["medium", "high"].includes(confidence?.level) ||
    coverage?.estimate_is_partial === true
  ) {
    return null;
  }
  return comparison;
}

export function buildInsight({
  breakdown,
  contributingTotal,
  confidence,
  estimatedDetails,
  attentionDetails,
  topActivity,
  coverageSummary,
  assumptionCount,
  fallbackCount,
  clarification,
}) {
  const points = [];
  const sortedCategories = [...(breakdown || [])].sort((a, b) => b.amount - a.amount);
  const topCategory = sortedCategories[0];
  const secondCategory = sortedCategories[1];
  const topActivityShare = topActivity
    ? percentage(includedAmount(topActivity), contributingTotal)
    : 0;

  if (topActivity && topActivityShare >= 60) {
    points.push(
      `${activityLabel(topActivity.activity_type)} makes up ${topActivityShare}% of the estimated footprint, so today's result is concentrated in one activity.`
    );
  } else if (topCategory && topCategory.percentage >= 50) {
    const activityCount =
      topCategory.estimatedCount > 1
        ? ` across ${topCategory.estimatedCount} estimated activities`
        : "";
    points.push(
      `${topCategory.label} accounts for ${topCategory.percentage}% of the estimated footprint${activityCount}.`
    );
  } else if (topCategory && secondCategory) {
    points.push(
      `The estimate is split most between ${topCategory.label} (${topCategory.percentage}%) and ${secondCategory.label} (${secondCategory.percentage}%).`
    );
  } else if (topCategory) {
    points.push(`${topCategory.label} is the only estimated category in this result.`);
  }

  const dailyContext = dailyReferenceInsight({
    total: contributingTotal,
    confidence,
    coverageSummary,
  });
  if (dailyContext) {
    points.push(dailyContext);
  }

  const bottleneck = confidenceBottleneck(estimatedDetails);
  if (bottleneck) {
    points.push(bottleneck);
  }

  if (coverageSummary?.partial && attentionDetails?.length && points.length < 3) {
    points.push(partialInsight(attentionDetails, clarification));
  }

  if (topActivity && topActivityShare < 60 && points.length < 3) {
    points.push(
      `${activityLabel(topActivity.activity_type)} is the largest single activity at ${formatNumber(includedAmount(topActivity))} ${topActivity.unit || "kg"} CO2e.`
    );
  }

  if (
    points.length < 2 &&
    estimatedDetails?.length > 0 &&
    assumptionCount === 0 &&
    fallbackCount === 0 &&
    confidence?.level === "high"
  ) {
    points.push(
      "The included activities did not need assumptions, so this estimate is relatively direct."
    );
  }

  if (
    points.length < 2 &&
    estimatedDetails?.length > 0 &&
    ["medium", "low"].includes(confidence?.level)
  ) {
    points.push("The estimate is useful for direction, but one or more inputs still limited confidence.");
  }

  return uniqueMessages(points).slice(0, 3);
}

export function buildCoverageSummary(coverage, details) {
  const representedFallback = details.length;
  const estimatedFallback = details.filter((detail) => INCLUDED_STATUSES.has(detail.status))
    .length;
  const needDetailsFallback = details.filter((detail) => ATTENTION_STATUSES.has(detail.status))
    .length;
  const notIncludedFallback = details.filter((detail) => detail.status === "not_estimated")
    .length;

  const notRepresented =
    coverage?.not_represented_count ??
    coverage?.detected_but_not_represented_count ??
    coverage?.unrepresented_activity_count ??
    null;

  return {
    found: coverage?.represented_activity_count ?? representedFallback,
    estimated: coverage?.included_in_total_count ?? estimatedFallback,
    needDetails:
      (coverage?.unresolved_count ?? null) !== null || (coverage?.failed_count ?? null) !== null
        ? (coverage?.unresolved_count || 0) + (coverage?.failed_count || 0)
        : needDetailsFallback,
    notIncluded: coverage?.not_estimated_count ?? notIncludedFallback,
    notRepresented,
    partial:
      coverage?.estimate_is_partial ??
      details.some((detail) => ATTENTION_STATUSES.has(detail.status)),
    fromBackend: Boolean(coverage),
  };
}

export function buildQuality({
  confidence,
  coverageSummary,
  assumptionActivityCount,
  assumptionCount,
  fallbackCount,
  largestCategoryLabels,
}) {
  const reasons = [];
  if (assumptionActivityCount > 0) {
    reasons.push(
      `${assumptionActivityCount} ${assumptionActivityCount === 1 ? "activity used" : "activities used"} assumptions`
    );
  }
  if (fallbackCount > 0) {
    reasons.push(
      fallbackCount === 1
        ? "1 activity is an approximate estimate"
        : `${fallbackCount} activities are approximate estimates`
    );
  }
  if (coverageSummary?.needDetails > 0) {
    reasons.push(
      `${coverageSummary.needDetails} ${coverageSummary.needDetails === 1 ? "activity needs" : "activities need"} more detail`
    );
  }
  if (coverageSummary?.partial) {
    reasons.push("The represented estimate is partial");
  }
  if (largestCategoryLabels?.length > 0) {
    reasons.push(
      `${largestCategoryLabels.length === 1 ? "Largest estimated category was" : "Largest estimated categories were"} ${joinLabels(largestCategoryLabels)}`
    );
  }
  if (reasons.length === 0 && assumptionCount === 0) {
    reasons.push("Included activities had enough detail for the current estimate");
  }

  return {
    label: confidenceLabel(confidence) || "Unknown",
    level: confidence?.level || "unknown",
    reasons: reasons.slice(0, 4),
  };
}

const CONFIDENCE_TONES = {
  high: {
    badgeClass: "border-emerald-200 bg-emerald-100 text-emerald-950",
    cardClass: "border-emerald-200 bg-emerald-50 text-emerald-950 shadow-emerald-900/5",
    dotClass: "bg-emerald-500",
    textClass: "text-emerald-700",
  },
  medium: {
    badgeClass: "border-yellow-200 bg-yellow-100 text-yellow-950",
    cardClass: "border-yellow-200 bg-yellow-50 text-yellow-950 shadow-yellow-900/5",
    dotClass: "bg-yellow-500",
    textClass: "text-yellow-700",
  },
  low: {
    badgeClass: "border-red-200 bg-red-100 text-red-950",
    cardClass: "border-red-200 bg-red-50 text-red-950 shadow-red-900/5",
    dotClass: "bg-red-500",
    textClass: "text-red-700",
  },
  unknown: {
    badgeClass: "border-stone-200 bg-stone-100 text-stone-800",
    cardClass: "border-stone-200 bg-white text-stone-950 shadow-stone-900/5",
    dotClass: "bg-stone-400",
    textClass: "text-stone-700",
  },
};

export function confidenceTone(confidenceOrLevel) {
  const level =
    typeof confidenceOrLevel === "string"
      ? confidenceOrLevel
      : confidenceOrLevel?.level;
  return CONFIDENCE_TONES[level] || CONFIDENCE_TONES.unknown;
}

export function buildClarificationPriority(suggestions, attentionDetails) {
  const backendSuggestion = Array.isArray(suggestions) ? suggestions[0] : null;
  if (backendSuggestion) {
    return {
      title: backendSuggestion.title || "Most useful detail to add",
      prompt:
        backendSuggestion.prompt ||
        backendSuggestion.question ||
        backendSuggestion.message ||
        "Add the missing detail requested by the estimate.",
      rawText: backendSuggestion.raw_text || backendSuggestion.rawText || null,
      category: backendSuggestion.category || null,
      guidanceOnly: backendSuggestion.guidance_only !== false,
    };
  }

  const ranked = attentionDetails
    .map((detail) => ({ detail, priority: clarificationPriority(detail) }))
    .filter((item) => item.priority > 0)
    .sort((a, b) => b.priority - a.priority);

  if (!ranked.length) {
    return null;
  }

  const detail = ranked[0].detail;
  return {
    title: "Most useful detail to add",
    prompt: clarificationPrompt(detail),
    rawText: detail.raw_text || null,
    category: detail.category,
    guidanceOnly: true,
  };
}

export function categoryLabel(category) {
  return CATEGORY_LABELS[category] || formatLabel(category);
}

export function categoryMeta(category) {
  return CATEGORIES.find((item) => item.key === category) || CATEGORIES[2];
}

export function activityLabel(activityType) {
  return formatLabel(activityType || "activity");
}

export function confidenceLabel(confidence) {
  if (!confidence?.level) {
    return null;
  }
  return formatLabel(confidence.level);
}

export function technicalConfidence(confidence) {
  const label = confidenceLabel(confidence) || "Unknown";
  return confidence?.score === undefined || confidence?.score === null
    ? label
    : `${label} (${formatNumber(confidence.score)})`;
}

export function formatNumber(value) {
  return Number(value || 0).toFixed(2);
}

export function parameterSummary(parameters = {}) {
  const consumed = new Set();
  const parts = [];

  COMBINED_PARAMETER_KEYS.forEach(([amountKey, unitKey]) => {
    if (parameters[amountKey] !== undefined && parameters[amountKey] !== null) {
      const unit = parameters[unitKey] ? ` ${parameters[unitKey]}` : "";
      parts.push(`${formatScalar(parameters[amountKey])}${unit}`);
      consumed.add(amountKey);
      consumed.add(unitKey);
    }
  });

  Object.entries(parameters).forEach(([key, value]) => {
    if (
      consumed.has(key) ||
      INTERNAL_PARAMETER_KEYS.has(key) ||
      value === undefined ||
      value === null
    ) {
      return;
    }
    parts.push(`${formatLabel(key)}: ${formatScalar(value)}`);
  });

  return parts.join(" | ");
}

export function geospatialSummary(detail) {
  const parameters = detail?.parameters || {};
  const lines = [];
  if (parameters.origin || parameters.destination) {
    const origin = parameters.origin_place_name || parameters.origin;
    const destination = parameters.destination_place_name || parameters.destination;
    lines.push({
      label: "Route",
      value: [origin, destination].filter(Boolean).join(" to "),
    });
    const fuzzyMatches = fuzzyPlaceMatchMessages(parameters);
    if (fuzzyMatches.length > 0) {
      lines.push({
        label: "Place matching",
        value: fuzzyMatches.join("; "),
      });
    }
    if (parameters.route_path_place_names) {
      lines.push({
        label: "Route path",
        value: parameters.route_path_place_names,
      });
    }
    if (parameters.distance_source) {
      lines.push({
        label: "Distance source",
        value: `${routeDistanceSourceLabel(parameters.distance_source)}${
          parameters.route_exact === false ? " (approximate)" : ""
        }`,
      });
    }
  }

  if (parameters.region || parameters.region_name) {
    lines.push({
      label: "Electricity region",
      value: parameters.region_name
        ? `${parameters.region_name} (${parameters.region})`
        : parameters.region,
    });
  }

  return lines.length > 0 ? lines : null;
}

export function consumerAssumptionMessage(assumption) {
  const message = assumption?.message || String(assumption);
  if (/local fallback factor/i.test(message)) {
    return "Used an approximate emissions factor because a more specific estimate was not available.";
  }
  return message
    .replace(/for the Climatiq estimate/gi, "for this estimate")
    .replace(/\bClimatiq\b/gi, "an emissions data source");
}

function routeDistanceSourceLabel(source) {
  if (!source) {
    return null;
  }
  const normalized = String(source).toLowerCase();
  if (normalized.includes("road_network") || normalized.includes("route_network_road")) {
    return "Road network route";
  }
  if (normalized.includes("gtfs") || normalized.includes("transit")) {
    return "Transit graph route";
  }
  if (normalized.includes("centroid")) {
    return "Centroid approximation";
  }
  if (normalized.includes("route_cache")) {
    return "Exact route cache";
  }
  return formatLabel(source);
}

function fuzzyPlaceMatchMessages(parameters) {
  return [
    ["origin", "Origin"],
    ["destination", "Destination"],
  ]
    .map(([key, label]) => {
      if (parameters[`${key}_match_type`] !== "fuzzy_alias") {
        return null;
      }
      const supplied = parameters[key];
      const matched = parameters[`${key}_place_name`] || parameters[`${key}_matched_alias`];
      if (!supplied || !matched) {
        return null;
      }
      return `${label} "${supplied}" matched to ${matched}`;
    })
    .filter(Boolean);
}

export function improvementGuidance(detail) {
  if (!detail?.confidence || detail.confidence.level === "high") {
    return null;
  }

  const confidenceParts = [
    ["parameter", detail.parameter_confidence?.score],
    ["factor", detail.factor_confidence?.score],
    ["source", detail.source_confidence?.score],
  ].filter(([, score]) => typeof score === "number");

  if (detail.status === "fallback_estimated" || detail.source === "fallback") {
    return "This uses an approximate local factor because a verified provider estimate was not available.";
  }

  if (confidenceParts.length > 0) {
    const [weakestPart] = confidenceParts.reduce((weakest, current) =>
      current[1] < weakest[1] ? current : weakest
    );

    if (weakestPart === "parameter") {
      return "Adding a clearer quantity, unit, distance, weight, or duration would improve this estimate.";
    }
    if (weakestPart === "factor") {
      return "A more specific emissions factor would improve this estimate. Your activity details were understood, but the available factor was broad.";
    }
    if (weakestPart === "source") {
      return "A stronger emissions data source would improve this estimate.";
    }
  }

  if (detail.factor?.score !== undefined && detail.factor?.score !== null) {
    return "A more specific emissions factor would improve this estimate. Your activity details were understood, but the available factor was broad.";
  }

  return "More specific activity details would improve this estimate.";
}

export function formatLabel(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function statusLabel(status) {
  return formatLabel(status);
}

export function sourceLabel(source) {
  return {
    climatiq: "Climatiq",
    fallback: "Local fallback",
    none: "No estimate",
    unresolved: "Unresolved",
  }[source] || formatLabel(source);
}

export function friendlyStatusCopy(status) {
  return {
    unresolved: "We could not estimate this activity yet.",
    failed: "This activity could not be estimated right now.",
    not_estimated: "This activity was recognised but is not included in estimated emissions.",
  }[status] || statusLabel(status);
}

function includedAmount(detail) {
  const amount = Number(detail.co2e);
  return Number.isFinite(amount) && amount > 0 ? amount : 0;
}

function formatScalar(value) {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : String(value);
  }
  if (Array.isArray(value)) {
    return value.map(formatScalar).join(", ");
  }
  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }
  return String(value);
}

function topEstimatedActivity(estimatedDetails) {
  if (!estimatedDetails.length) {
    return null;
  }
  const topAmount = Math.max(...estimatedDetails.map((detail) => includedAmount(detail)));
  if (topAmount <= 0) {
    return null;
  }
  const tied = estimatedDetails.filter(
    (detail) => Math.abs(includedAmount(detail) - topAmount) < 1e-9
  );
  return tied.length === 1 ? tied[0] : null;
}

function percentage(amount, total) {
  return total > 0 ? Math.round((amount / total) * 100) : 0;
}

function joinLabels(labels) {
  if (!labels?.length) {
    return "";
  }
  if (labels.length === 1) {
    return labels[0];
  }
  if (labels.length === 2) {
    return `${labels[0]} and ${labels[1]}`;
  }
  return `${labels.slice(0, -1).join(", ")}, and ${labels[labels.length - 1]}`;
}

function confidenceBottleneck(estimatedDetails = []) {
  const candidates = estimatedDetails
    .filter((detail) => detail.confidence?.level && detail.confidence.level !== "high")
    .sort((a, b) => {
      const amountDifference = includedAmount(b) - includedAmount(a);
      if (Math.abs(amountDifference) > 1e-9) {
        return amountDifference;
      }
      return (a.confidence?.score ?? 1) - (b.confidence?.score ?? 1);
    });

  if (!candidates.length) {
    return null;
  }

  const detail = candidates[0];
  const label = activityLabel(detail.activity_type);
  const confidence = confidenceLabel(detail.confidence)?.toLowerCase() || "lower";

  if (detail.status === "fallback_estimated" || detail.source === "fallback") {
    return `${label} is included in the total, but it relies on an approximate local emissions factor.`;
  }

  const weakestPart = weakestConfidencePart(detail);
  if (weakestPart === "parameter") {
    return `${label} has ${confidence} confidence because the activity quantity or unit was still broad.`;
  }
  if (weakestPart === "factor") {
    return `${label} had clear activity details, but the matched emissions factor was broad.`;
  }
  if (weakestPart === "source") {
    return `${label} is limited mostly by emissions source confidence, not the activity details.`;
  }
  if (detail.assumptions?.length > 0) {
    return `${label} carries assumptions, so it is a useful activity to verify if the total feels off.`;
  }

  return null;
}

function weakestConfidencePart(detail) {
  const confidenceParts = [
    ["parameter", detail.parameter_confidence?.score],
    ["factor", detail.factor_confidence?.score],
    ["source", detail.source_confidence?.score],
  ].filter(([, score]) => typeof score === "number");

  if (!confidenceParts.length) {
    return null;
  }

  return confidenceParts.reduce((weakest, current) =>
    current[1] < weakest[1] ? current : weakest
  )[0];
}

function partialInsight(attentionDetails, clarification) {
  const detail = attentionDetails[0];
  const label = activityLabel(detail.activity_type);
  if (clarification?.prompt) {
    return `${label} was detected but left out of the total; answering "${clarification.prompt}" would make the summary more complete.`;
  }
  return `${label} was detected but left out of the total, so the current number should be read as partial.`;
}

function dailyReferenceInsight({ total, confidence, coverageSummary }) {
  if (
    total <= 0 ||
    coverageSummary?.partial ||
    !["medium", "high"].includes(confidence?.level)
  ) {
    return null;
  }

  const ratio = total / AU_DAILY_REFERENCE.kgCo2ePerDay;
  if (ratio >= 1) {
    return `This included estimate is about ${formatRatio(ratio)} times the ${AU_DAILY_REFERENCE.label}.`;
  }

  return `This included estimate is about ${formatPercent(ratio)} of the ${AU_DAILY_REFERENCE.label}.`;
}

function formatRatio(ratio) {
  if (ratio >= 10) {
    return String(Math.round(ratio));
  }
  return ratio.toFixed(1).replace(/\.0$/, "");
}

function formatPercent(ratio) {
  const percentageValue = ratio * 100;
  if (percentageValue < 1) {
    return "less than 1%";
  }
  return `${Math.round(percentageValue)}%`;
}

function uniqueMessages(messages) {
  return messages.filter((message, index, allMessages) => {
    return message && allMessages.indexOf(message) === index;
  });
}

function clarificationPriority(detail) {
  const parameters = detail.parameters || {};
  if (detail.category === "transport" && parameters.distance === undefined) {
    return 40;
  }
  if (detail.category === "waste" && parameters.weight === undefined) {
    return 35;
  }
  if (
    detail.category === "energy" &&
    parameters.energy === undefined &&
    parameters.duration === undefined
  ) {
    return 30;
  }
  if (detail.category === "goods_services") {
    return 20;
  }
  return ATTENTION_STATUSES.has(detail.status) ? 10 : 0;
}

function clarificationPrompt(detail) {
  const parameters = detail.parameters || {};
  if (detail.category === "transport" && parameters.distance === undefined) {
    return "How far was this trip?";
  }
  if (detail.category === "waste" && parameters.weight === undefined) {
    return "How much did this waste weigh?";
  }
  if (
    detail.category === "energy" &&
    parameters.energy === undefined &&
    parameters.duration === undefined
  ) {
    return "How long was this used, or how much electricity was used?";
  }
  if (detail.category === "goods_services") {
    return "What was bought, how many items, or roughly how much was spent?";
  }
  return "What extra detail would make this activity clearer?";
}
