import React from "react";
import {
  activityLabel,
  formatLabel,
  formatNumber,
  sourceLabel,
  statusLabel,
  technicalConfidence,
} from "./resultPresentation";

export default function DeveloperDetailsAccordion({ estimate, details }) {
  return (
    <details
      className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
      data-testid="developer-details"
    >
      <summary className="cursor-pointer font-semibold text-gray-900">
        How this estimate was calculated
      </summary>
      <div className="mt-4 space-y-4 text-sm text-gray-700">
        {estimate.total?.confidence && (
          <p className="rounded-md bg-gray-50 p-3">
            <strong>Total estimate confidence:</strong>{" "}
            {technicalConfidence(estimate.total.confidence)}
          </p>
        )}
        {details.length === 0 && <p>No activity calculation details are available.</p>}
        {details.map((detail, index) => (
          <TechnicalDetail
            key={`${detail.raw_text || detail.activity_type || index}-${index}`}
            detail={detail}
          />
        ))}
      </div>
    </details>
  );
}

function TechnicalDetail({ detail }) {
  return (
    <article className="rounded-lg border border-gray-200 p-4">
      <h3 className="font-semibold text-gray-900">{activityLabel(detail.activity_type)}</h3>
      {detail.raw_text && (
        <p className="mt-2">
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
          <h4 className="font-semibold text-gray-800">Parameters</h4>
          <dl className="mt-2 grid gap-2 rounded-md bg-gray-50 p-3 sm:grid-cols-2">
            {Object.entries(detail.parameters).map(([key, value]) => (
              <TechnicalField key={key} label={formatLabel(key)} value={String(value)} />
            ))}
          </dl>
        </div>
      )}

      {detail.factor && (
        <div className="mt-4">
          <h4 className="font-semibold text-gray-800">Factor</h4>
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

      <TechnicalRecords title="Assumptions" records={detail.assumptions} />
      <TechnicalRecords title="Issues" records={detail.issues} />
    </article>
  );
}

function TechnicalField({ label, value }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</dt>
      <dd className="mt-1 text-gray-900">{value}</dd>
    </div>
  );
}

function TechnicalRecords({ title, records = [] }) {
  if (!records.length) {
    return null;
  }
  return (
    <div className="mt-4">
      <h4 className="font-semibold text-gray-800">{title}</h4>
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
