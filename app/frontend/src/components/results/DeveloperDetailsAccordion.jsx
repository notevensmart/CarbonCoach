import React from "react";
import {
  activityLabel,
  formatLabel,
  formatNumber,
  sourceLabel,
  statusLabel,
  technicalConfidence,
} from "./resultPresentation";

export default function DeveloperDetailsAccordion({
  estimate,
  details,
  comparison,
  coverageSummary,
  visibleComparison,
}) {
  const factorDetails = details.filter((detail) => detail.factor || detail.factor_diagnostics);

  return (
    <section
      aria-labelledby="details-title"
      className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm"
      data-testid="developer-details"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
            Engineering view
          </p>
          <h2 id="details-title" className="text-xl font-semibold text-stone-950">
            How this estimate was calculated
          </h2>
        </div>
        <span className="w-fit rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-xs font-semibold text-stone-600">
          Technical details
        </span>
      </div>

      <div className="mt-5 space-y-3 text-sm text-stone-700">
        <TechnicalSection title="Response Summary" defaultOpen>
          <dl className="grid gap-3 sm:grid-cols-2">
            <TechnicalField label="Response version" value={estimate.version || "v2"} />
            <TechnicalField
              label="Total estimate"
              value={`${formatNumber(estimate.total?.co2e)} ${estimate.total?.unit || "kg"} CO2e`}
            />
            {estimate.total?.confidence && (
              <TechnicalField
                label="Total estimate confidence"
                value={technicalConfidence(estimate.total.confidence)}
              />
            )}
            <TechnicalField
              label="Included activity count"
              value={String(coverageSummary?.estimated ?? details.length)}
            />
          </dl>
          {estimate.total?.source_breakdown && (
            <div className="mt-4">
              <h4 className="font-semibold text-stone-900">Source breakdown</h4>
              <dl className="mt-2 grid gap-2 rounded-xl bg-stone-50 p-3 sm:grid-cols-3">
                {Object.entries(estimate.total.source_breakdown).map(([key, value]) => (
                  <TechnicalField
                    key={key}
                    label={formatLabel(key)}
                    value={`${formatNumber(value)} ${estimate.total?.unit || "kg"} CO2e`}
                  />
                ))}
              </dl>
            </div>
          )}
        </TechnicalSection>

        <TechnicalSection title="Coverage" defaultOpen>
          {coverageSummary ? (
            <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <TechnicalField label="Represented activities" value={coverageSummary.found} />
              <TechnicalField label="Included in total" value={coverageSummary.estimated} />
              <TechnicalField label="Need details" value={coverageSummary.needDetails} />
              <TechnicalField label="Not included" value={coverageSummary.notIncluded} />
              <TechnicalField
                label="Not represented yet"
                value={
                  coverageSummary.notRepresented === null ||
                  coverageSummary.notRepresented === undefined
                    ? "Not exposed"
                    : coverageSummary.notRepresented
                }
              />
              <TechnicalField
                label="Partial estimate"
                value={coverageSummary.partial ? "Yes" : "No"}
              />
            </dl>
          ) : (
            <p>No coverage metadata was supplied.</p>
          )}
        </TechnicalSection>

        <TechnicalSection title="Per-Activity Details">
          {details.length === 0 && <p>No activity calculation details are available.</p>}
          <div className="space-y-3">
            {details.map((detail, index) => (
              <TechnicalDetail
                detail={detail}
                key={`${detail.raw_text || detail.activity_type || index}-${index}`}
              />
            ))}
          </div>
        </TechnicalSection>

        <TechnicalSection title="Factor Linking">
          {factorDetails.length === 0 ? (
            <p>No factor linking diagnostics were supplied for this response.</p>
          ) : (
            <div className="space-y-3">
              {factorDetails.map((detail, index) => (
                <FactorLinkingDetail
                  detail={detail}
                  key={`${detail.raw_text || detail.activity_type || index}-${index}`}
                />
              ))}
            </div>
          )}
        </TechnicalSection>

        {comparison && (
          <TechnicalSection title="Impact Comparison">
            {!visibleComparison && (
              <p className="mb-3 rounded-xl bg-amber-50 p-3 text-amber-950">
                This comparison was not shown in the primary result because the current display
                rules did not mark it eligible.
              </p>
            )}
            <ComparisonTechnicalDetail comparison={comparison} />
          </TechnicalSection>
        )}

        <TechnicalSection title="Raw JSON Preview">
          <pre className="max-h-96 overflow-auto rounded-xl bg-stone-950 p-4 text-xs text-stone-50">
            {JSON.stringify(estimate, null, 2)}
          </pre>
        </TechnicalSection>
      </div>
    </section>
  );
}

function TechnicalSection({ title, children, defaultOpen = false }) {
  return (
    <details className="rounded-xl border border-stone-200 bg-white p-4" open={defaultOpen}>
      <summary className="cursor-pointer font-semibold text-stone-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700">
        {title}
      </summary>
      <div className="mt-4">{children}</div>
    </details>
  );
}

function ComparisonTechnicalDetail({ comparison }) {
  return (
    <section className="rounded-xl border border-stone-200 p-4">
      <h3 className="font-semibold text-stone-950">Impact comparison calculation</h3>
      <dl className="mt-3 grid gap-2 sm:grid-cols-2">
        <TechnicalField label="Comparison key" value={comparison.key} />
        <TechnicalField label="Reference label" value={comparison.reference_label} />
        <TechnicalField
          label="Input total kg CO2e"
          value={`${comparison.input_total_kg_co2e} kg CO2e`}
        />
        <TechnicalField
          label="Conversion factor used"
          value={`${comparison.kg_co2e_per_unit} kg CO2e/${comparison.unit}`}
        />
        <TechnicalField
          label="Calculated comparison amount"
          value={`${comparison.amount} ${comparison.unit}`}
        />
      </dl>
      <p className="mt-3">
        <strong>Applicability:</strong> {comparison.applicability}
      </p>
      <p className="mt-2">
        <strong>Source/provenance:</strong> {comparison.source_note}
      </p>
    </section>
  );
}

function TechnicalDetail({ detail }) {
  return (
    <details className="rounded-xl border border-stone-200 p-4">
      <summary className="cursor-pointer font-semibold text-stone-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700">
        {activityLabel(detail.activity_type)}
      </summary>
      <div className="mt-3">
        {detail.raw_text && (
          <p>
            <strong>Raw event text:</strong> {detail.raw_text}
          </p>
        )}
        <dl className="mt-3 grid gap-2 sm:grid-cols-2">
          <TechnicalField label="Status" value={statusLabel(detail.status)} />
          <TechnicalField label="Source" value={sourceLabel(detail.source)} />
          {detail.parameter_confidence && (
            <TechnicalField
              label="Parameter confidence"
              value={technicalConfidence(detail.parameter_confidence)}
            />
          )}
          {detail.factor_confidence && (
            <TechnicalField
              label="Factor confidence"
              value={technicalConfidence(detail.factor_confidence)}
            />
          )}
          {detail.confidence && (
            <TechnicalField
              label="Estimate confidence"
              value={technicalConfidence(detail.confidence)}
            />
          )}
          {detail.source_confidence && (
            <TechnicalField
              label="Source confidence"
              value={technicalConfidence(detail.source_confidence)}
            />
          )}
        </dl>

        {detail.parameters && Object.keys(detail.parameters).length > 0 && (
          <div className="mt-4">
            <h4 className="font-semibold text-stone-900">Parameters</h4>
            <dl className="mt-2 grid gap-2 rounded-xl bg-stone-50 p-3 sm:grid-cols-2">
              {Object.entries(detail.parameters).map(([key, value]) => (
                <TechnicalField key={key} label={formatLabel(key)} value={formatTechnicalValue(value)} />
              ))}
            </dl>
          </div>
        )}

        <TechnicalRecords title="Assumptions" records={detail.assumptions} />
        <TechnicalRecords title="Issues" records={detail.issues} />
      </div>
    </details>
  );
}

function FactorLinkingDetail({ detail }) {
  return (
    <article className="rounded-xl border border-stone-200 p-4">
      <h3 className="font-semibold text-stone-950">{activityLabel(detail.activity_type)}</h3>
      {detail.raw_text && <p className="mt-1 text-stone-600">{detail.raw_text}</p>}
      {detail.factor && (
        <div className="mt-4">
          <h4 className="font-semibold text-stone-900">Selected factor</h4>
          {detail.factor.name && <p className="mt-1">{detail.factor.name}</p>}
          {detail.factor.activity_id && (
            <p className="mt-1 break-all font-mono text-xs">{detail.factor.activity_id}</p>
          )}
          {detail.factor.score !== undefined && detail.factor.score !== null && (
            <p className="mt-2">
              <strong>Factor fit:</strong> {formatNumber(detail.factor.score)}
            </p>
          )}
          {detail.factor.match_reasons?.length > 0 && (
            <>
              <h5 className="mt-3 font-semibold">Match reasons</h5>
              <ul className="mt-1 list-disc pl-5">
                {detail.factor.match_reasons.map((reason, index) => (
                  <li key={`${reason}-${index}`}>{reason}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
      {detail.factor_diagnostics && (
        <FactorDiagnostics diagnostics={detail.factor_diagnostics} />
      )}
    </article>
  );
}

function FactorDiagnostics({ diagnostics }) {
  return (
    <div className="mt-4">
      <h4 className="font-semibold text-stone-900">Factor retrieval diagnostics</h4>
      <dl className="mt-2 grid gap-2 rounded-xl bg-stone-50 p-3 sm:grid-cols-2">
        <TechnicalField label="Factor intent" value={diagnostics.intent_key || "None"} />
        {diagnostics.intent && (
          <TechnicalField label="Intent payload" value={formatTechnicalValue(diagnostics.intent)} />
        )}
        <TechnicalField label="Search query" value={diagnostics.search_query || "None"} />
        {diagnostics.selector_filters && (
          <TechnicalField
            label="Selector filters"
            value={formatTechnicalValue(diagnostics.selector_filters)}
          />
        )}
        <TechnicalField
          label="Candidate count"
          value={String(diagnostics.candidate_count ?? 0)}
        />
        <TechnicalField
          label="Selected factor"
          value={diagnostics.selected_activity_id || "None"}
        />
        <TechnicalField
          label="Fallback used"
          value={diagnostics.fallback_used ? "Yes" : "No"}
        />
        {diagnostics.fallback_reason && (
          <TechnicalField label="Fallback reason" value={diagnostics.fallback_reason} />
        )}
        {diagnostics.fallback_assumption_code && (
          <TechnicalField
            label="Fallback assumption"
            value={diagnostics.fallback_assumption_code}
          />
        )}
      </dl>
      {diagnostics.selected_reason && (
        <p className="mt-2">
          <strong>Selected reason:</strong> {diagnostics.selected_reason}
        </p>
      )}
      {diagnostics.top_rejections?.length > 0 && (
        <>
          <h5 className="mt-3 font-semibold">Rejected candidates</h5>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {diagnostics.top_rejections.map((rejection, index) => (
              <li key={`${rejection.activity_id || index}-${index}`}>
                {rejection.activity_id && (
                  <span className="break-all font-mono text-xs">
                    {rejection.activity_id}:{" "}
                  </span>
                )}
                {rejection.reason || formatTechnicalValue(rejection)}
              </li>
            ))}
          </ul>
        </>
      )}
      {diagnostics.attempts?.length > 0 && (
        <>
          <h5 className="mt-3 font-semibold">Attempts</h5>
          <pre className="mt-1 max-h-64 overflow-auto rounded-xl bg-stone-950 p-3 text-xs text-stone-50">
            {JSON.stringify(diagnostics.attempts, null, 2)}
          </pre>
        </>
      )}
    </div>
  );
}

function TechnicalField({ label, value }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</dt>
      <dd className="mt-1 break-words text-stone-950">{formatTechnicalValue(value)}</dd>
    </div>
  );
}

function TechnicalRecords({ title, records = [] }) {
  if (!records.length) {
    return null;
  }
  return (
    <div className="mt-4">
      <h4 className="font-semibold text-stone-900">{title}</h4>
      <ul className="mt-1 list-disc space-y-1 pl-5">
        {records.map((record, index) => (
          <li key={`${record.code || title}-${index}`}>
            {record.code && <span className="font-mono text-xs">{record.code}: </span>}
            {record.message || String(record)}
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatTechnicalValue(value) {
  if (value === undefined || value === null || value === "") {
    return "None";
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}
