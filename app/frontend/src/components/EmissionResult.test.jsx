import React from "react";
import { render, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom";

import EmissionResult from "./EmissionResult";

test("renders V2 totals, event transparency, and unknown entity details generically", () => {
  render(<EmissionResult response={v2Response} />);

  expect(screen.getByText("3.14 kg CO2e")).toBeInTheDocument();
  expect(screen.getByText("Medium (0.72)")).toBeInTheDocument();
  expect(screen.getByText("Source breakdown")).toBeInTheDocument();
  expect(screen.getByText("2.00 kg")).toBeInTheDocument();

  const fallbackCard = screen
    .getByText('"I took a ride in a BMW X5."')
    .closest("article");
  expect(within(fallbackCard).getByText("Fallback Estimated")).toBeInTheDocument();
  expect(within(fallbackCard).getByText("Local fallback")).toBeInTheDocument();
  expect(within(fallbackCard).getByText("Factor confidence")).toBeInTheDocument();
  expect(within(fallbackCard).getAllByText("Medium (0.55)").length).toBeGreaterThanOrEqual(2);
  expect(within(fallbackCard).getByText("BMW X5")).toBeInTheDocument();
  expect(within(fallbackCard).getByText(/vehicle.named.default_petrol_medium/)).toBeInTheDocument();
  expect(within(fallbackCard).getByText(/vehicle.named_model.unmapped/)).toBeInTheDocument();

  expect(screen.getByText("Climatiq")).toBeInTheDocument();
  expect(screen.getByText("Factor fit:")).toBeInTheDocument();
  expect(screen.getByText("normalized fuel_type matched: electric")).toBeInTheDocument();
});

test("keeps unresolved and not estimated activities visible without optional lists", () => {
  render(<EmissionResult response={v2Response} />);

  const attention = screen.getByText("Activities needing attention").closest("section");
  const unresolvedCard = within(attention)
    .getByText('"I used an electric scooter for 4 km."')
    .closest("article");
  const walkingCard = within(attention)
    .getByText('"I walked 2 km."')
    .closest("article");
  expect(within(unresolvedCard).getAllByText("Unresolved")).toHaveLength(2);
  expect(within(walkingCard).getByText("Not Estimated")).toBeInTheDocument();
  expect(within(walkingCard).getByText("No estimate")).toBeInTheDocument();
});

test("continues to render a V1 response when the configured endpoint targets V1", () => {
  render(
    <EmissionResult
      response={{
        result: {
          co2e: 1.25,
          unit: "kg",
          summary: "Legacy result",
          details: [],
        },
      }}
    />
  );

  expect(screen.getByText("1.25 kg CO2e")).toBeInTheDocument();
  expect(screen.getByText("Legacy result")).toBeInTheDocument();
});

const v2Response = {
  version: "v2",
  total: {
    co2e: 3.14,
    unit: "kg",
    confidence: { score: 0.72, level: "medium" },
    source_breakdown: {
      estimated: 1.14,
      fallback_estimated: 2,
      not_estimated: 0,
    },
  },
  details: [
    {
      raw_text: "I took a ride in a BMW X5.",
      category: "transport",
      activity_type: "car_ride",
      status: "fallback_estimated",
      co2e: 2,
      unit: "kg",
      source: "fallback",
      confidence: { score: 0.55, level: "medium" },
      parameter_confidence: { score: 0.6, level: "medium" },
      factor_confidence: { score: 0.55, level: "medium" },
      source_confidence: { score: 0.55, level: "medium" },
      parameters: { vehicle_description: "BMW X5", distance: 5, distance_unit: "km" },
      assumptions: [
        {
          code: "vehicle.named.default_petrol_medium",
          message: "Used a generic passenger-car default.",
        },
      ],
      issues: [
        {
          code: "vehicle.named_model.unmapped",
          message: "No verified vehicle record matched this name.",
        },
      ],
    },
    {
      raw_text: "I drove my electric car for 10 km.",
      category: "transport",
      activity_type: "car_ride",
      status: "estimated",
      co2e: 1.14,
      unit: "kg",
      source: "climatiq",
      confidence: { score: 0.92, level: "high" },
      parameter_confidence: { score: 0.95, level: "high" },
      factor_confidence: { score: 0.92, level: "high" },
      source_confidence: { score: 1, level: "high" },
      parameters: { distance: 10, distance_unit: "km", fuel_type: "electric" },
      assumptions: [],
      issues: [],
      factor: {
        activity_id: "fixture.electric.car",
        name: "Electric passenger car",
        score: 0.91,
        match_reasons: ["normalized fuel_type matched: electric"],
      },
    },
    {
      raw_text: "I used an electric scooter for 4 km.",
      category: "transport",
      activity_type: "generic_transport",
      status: "unresolved",
      source: "unresolved",
      confidence: { score: 0.2, level: "low" },
      parameters: {},
    },
    {
      raw_text: "I walked 2 km.",
      category: "transport",
      activity_type: "walking",
      status: "not_estimated",
      co2e: 0,
      unit: "kg",
      source: "none",
      confidence: { score: 0.9, level: "high" },
      parameters: { distance: 2, distance_unit: "km" },
    },
  ],
};
