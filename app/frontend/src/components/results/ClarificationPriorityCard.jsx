import React from "react";
import { categoryLabel } from "./resultPresentation";

export default function ClarificationPriorityCard({ clarification }) {
  if (!clarification) {
    return null;
  }

  return (
    <section
      aria-labelledby="clarification-priority-title"
      className="rounded-2xl border border-amber-200 bg-amber-50 p-5 shadow-sm"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">
        Next best clarification
      </p>
      <h2 id="clarification-priority-title" className="mt-1 text-xl font-semibold text-amber-950">
        {clarification.title || "Most useful detail to add"}
      </h2>
      <p className="mt-3 text-base font-medium text-amber-950">{clarification.prompt}</p>
      {clarification.rawText && (
        <p className="mt-3 rounded-xl bg-white/75 p-3 text-sm italic text-amber-900">
          &quot;{clarification.rawText}&quot;
        </p>
      )}
      <p className="mt-3 text-sm text-amber-900">
        {clarification.category ? `${categoryLabel(clarification.category)} detail` : "Guidance only"}
        {clarification.guidanceOnly ? " - guidance only for now." : "."}
      </p>
    </section>
  );
}
