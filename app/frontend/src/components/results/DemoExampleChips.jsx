import React from "react";

export const DEMO_EXAMPLES = [
  {
    label: "Commute Day",
    journal:
      "I drove 12 km in a diesel SUV, took a 5 km bus ride, and walked 2 km to lunch.",
  },
  {
    label: "Food + Waste",
    journal:
      "I bought coffee for $6, picked up groceries for $45, and threw away 500 g of plastic packaging.",
  },
  {
    label: "Household Energy",
    journal:
      "I used a 2 kW heater for 3 hours, cooked dinner in the oven for 45 minutes, and used 5 kWh of electricity.",
  },
  {
    label: "Messy Mixed Journal",
    journal:
      "Today I drove 7k in a toytoa camery, bought two shirts, recycled 500g of plastic, and used the heater for 3hrs.",
  },
  {
    label: "Low-Detail Journal",
    journal:
      "I travelled across town, bought a few things, used some electricity, and threw out packaging.",
  },
];

export default function DemoExampleChips({ onSelect }) {
  return (
    <div aria-label="Demo examples" className="flex flex-wrap gap-2">
      {DEMO_EXAMPLES.map((example) => (
        <button
          className="cursor-pointer rounded-full border border-teal-200 bg-white px-3 py-2 text-sm font-semibold text-teal-900 shadow-sm transition-colors duration-200 hover:bg-teal-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
          key={example.label}
          onClick={() => onSelect(example.journal)}
          type="button"
        >
          {example.label}
        </button>
      ))}
    </div>
  );
}
