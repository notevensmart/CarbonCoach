export const INCLUDED_STATUSES = new Set(["estimated", "fallback_estimated"]);

export const CATEGORIES = [
  { key: "transport", label: "Transport", color: "#047857" },
  { key: "energy", label: "Energy", color: "#f59e0b" },
  { key: "goods_services", label: "Goods", color: "#2563eb" },
  { key: "waste", label: "Waste", color: "#7c3aed" },
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

const INTERNAL_PARAMETER_KEYS = new Set(["emissions_boundary", "factor_specificity"]);

export function buildDashboardModel(estimate) {
  const details = Array.isArray(estimate.details) ? estimate.details : [];
  const estimatedDetails = details.filter((detail) =>
    INCLUDED_STATUSES.has(detail.status)
  );
  const attentionDetails = details.filter((detail) =>
    ["unresolved", "failed"].includes(detail.status)
  );
  const notIncludedDetails = details.filter(
    (detail) => detail.status === "not_estimated"
  );

  const categories = CATEGORIES.map((category) => ({
    ...category,
    amount: estimatedDetails
      .filter((detail) => detail.category === category.key)
      .reduce((sum, detail) => sum + includedAmount(detail), 0),
  })).filter((category) => category.amount > 0);
  const contributingTotal = categories.reduce(
    (sum, category) => sum + category.amount,
    0
  );

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
    percentage: Math.round((category.amount / contributingTotal) * 100),
  }));

  return {
    total: contributingTotal,
    unit: estimate.total?.unit || "kg",
    confidence: estimate.total?.confidence,
    estimatedDetails,
    attentionDetails,
    notIncludedDetails,
    details,
    breakdown,
    mainDriver,
    comparison: displayableComparison(
      estimate.comparison,
      contributingTotal,
      estimate.total?.confidence
    ),
    insight: buildInsight({
      mainDriver,
      hasContributingCategory: breakdown.length > 0,
      attentionCount: attentionDetails.length,
      confidence: estimate.total?.confidence,
      estimatedCount: estimatedDetails.length,
    }),
  };
}

export function displayableComparison(comparison, total, confidence) {
  if (
    !comparison?.message ||
    comparison.approximate !== true ||
    total <= 0 ||
    !["medium", "high"].includes(confidence?.level)
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
}) {
  const sentences = [];
  if (hasContributingCategory) {
    sentences.push(
      mainDriver === "Multiple categories"
        ? "Today's estimated footprint was spread across multiple categories."
        : `${mainDriver} was the largest part of today's estimated footprint.`
    );
  }
  if (attentionCount) {
    sentences.push(
      `${attentionCount} ${attentionCount === 1 ? "activity" : "activities"} could not yet be included in the estimate.`
    );
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

export function categoryLabel(category) {
  return CATEGORY_LABELS[category] || formatLabel(category);
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

function includedAmount(detail) {
  const amount = Number(detail.co2e);
  return Number.isFinite(amount) && amount > 0 ? amount : 0;
}

function formatScalar(value) {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : String(value);
  }
  return String(value);
}
