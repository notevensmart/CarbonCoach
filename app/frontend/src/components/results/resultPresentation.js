export const INCLUDED_STATUSES = new Set(["estimated", "fallback_estimated"]);
export const ATTENTION_STATUSES = new Set(["unresolved", "failed"]);

export const CATEGORIES = [
  {
    key: "transport",
    label: "Transport",
    color: "#0f766e",
    softClass: "bg-teal-50 text-teal-900 border-teal-100",
  },
  {
    key: "energy",
    label: "Energy",
    color: "#b45309",
    softClass: "bg-amber-50 text-amber-950 border-amber-100",
  },
  {
    key: "goods_services",
    label: "Goods",
    color: "#3b5bdb",
    softClass: "bg-blue-50 text-blue-950 border-blue-100",
  },
  {
    key: "waste",
    label: "Waste",
    color: "#6d5d4f",
    softClass: "bg-stone-100 text-stone-950 border-stone-200",
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
]);

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
    insight: buildInsight({
      mainDriver,
      hasContributingCategory: breakdown.length > 0,
      attentionCount: attentionDetails.length,
      confidence: estimate.total?.confidence,
      estimatedCount: estimatedDetails.length,
      topActivity,
      coverageSummary,
      assumptionCount,
      fallbackCount,
      largestCategoryLabels,
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
  mainDriver,
  hasContributingCategory,
  attentionCount,
  confidence,
  estimatedCount,
  topActivity,
  coverageSummary,
  assumptionCount,
  fallbackCount,
  largestCategoryLabels,
  clarification,
}) {
  const sentences = [];
  if (hasContributingCategory) {
    if (largestCategoryLabels?.length > 1) {
      sentences.push(
        `${joinLabels(largestCategoryLabels)} drove most of today's estimated footprint.`
      );
    } else {
      sentences.push(`${mainDriver} was the largest part of today's estimated footprint.`);
    }
  }
  if (topActivity && sentences.length < 2 && !coverageSummary?.partial) {
    sentences.push(
      `${activityLabel(topActivity.activity_type)} was the largest estimated activity.`
    );
  }
  if (sentences.length < 2 && attentionCount) {
    sentences.push(
      `${attentionCount} ${attentionCount === 1 ? "activity" : "activities"} could not yet be included in the estimate.`
    );
  }
  if (sentences.length < 2 && clarification?.prompt) {
    sentences.push(`The most useful next detail is: ${clarification.prompt}`);
  }
  if (sentences.length < 2 && (assumptionCount > 0 || fallbackCount > 0)) {
    sentences.push("Some activities used assumptions or approximate emissions factors.");
  }
  if (
    sentences.length < 2 &&
    estimatedCount > 0 &&
    ["medium", "low"].includes(confidence?.level)
  ) {
    sentences.push(
      "Treat this as an approximate guide because some details were uncertain or assumed."
    );
  }
  return sentences.join(" ");
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
    reasons: reasons.slice(0, 4),
  };
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

export function consumerAssumptionMessage(assumption) {
  const message = assumption?.message || String(assumption);
  if (/local fallback factor/i.test(message)) {
    return "Used an approximate emissions factor because a more specific estimate was not available.";
  }
  return message
    .replace(/for the Climatiq estimate/gi, "for this estimate")
    .replace(/\bClimatiq\b/gi, "an emissions data source");
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
