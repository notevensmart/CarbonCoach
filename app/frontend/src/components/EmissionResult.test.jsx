import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom";

import EmissionResult from "./EmissionResult";

test("renders an estimated heater with visible consumer assumptions", () => {
  render(
    <EmissionResult
      response={v2Response([
        includedDetail({
          raw_text: "I turned on the heater for 3 hours.",
          category: "energy",
          activity_type: "space_heater_use",
          co2e: 1.8,
          confidence: { score: 0.6, level: "medium" },
          parameters: { duration: 3, duration_unit: "hours", energy: 4.5, energy_unit: "kWh" },
          assumptions: [
            {
              code: "space_heater.default_power",
              message: "Assumed heater power of 1.5 kW because wattage was not provided.",
            },
          ],
        }),
      ])}
    />
  );

  const hero = screen.getByText("Today's Estimated Footprint").closest("section");
  expect(within(hero).getByText("1.80 kg CO2e")).toBeInTheDocument();
  expect(within(hero).getByText("Medium")).toBeInTheDocument();
  expect(within(hero).queryByText(/0\.60/)).not.toBeInTheDocument();

  const card = activityCard("Space Heater Use");
  expect(within(card).getByText("What we assumed")).toBeInTheDocument();
  expect(
    within(card).getByText("Assumed heater power of 1.5 kW because wattage was not provided.")
  ).toBeInTheDocument();
  expect(within(card).queryByText(/space_heater\.default_power/)).not.toBeInTheDocument();
});

test("renders an explicit high-confidence estimate without an assumptions block", () => {
  render(
    <EmissionResult
      response={v2Response([
        includedDetail({
          raw_text: "I used 5 kWh of electricity.",
          category: "energy",
          activity_type: "electricity_use",
          co2e: 2,
          confidence: { score: 0.95, level: "high" },
          parameters: { energy: 5, energy_unit: "kWh" },
        }),
      ], { score: 0.95, level: "high" })}
    />
  );

  const card = activityCard("Electricity Use");
  expect(within(card).getByText(/Confidence:/)).toHaveTextContent("Confidence: High");
  expect(within(card).queryByText("What we assumed")).not.toBeInTheDocument();
});

test("shows mixed contributing categories, main driver, and accessible breakdown values", () => {
  render(
    <EmissionResult
      response={v2Response([
        includedDetail({
          category: "transport",
          activity_type: "car_ride",
          co2e: 2,
          parameters: { distance: 10, distance_unit: "km" },
        }),
        includedDetail({
          category: "energy",
          activity_type: "electricity_use",
          co2e: 1,
          parameters: { energy: 2.5, energy_unit: "kWh" },
        }),
      ])}
    />
  );

  const hero = screen.getByText("Today's Estimated Footprint").closest("section");
  expect(within(hero).getByText("3.00 kg CO2e")).toBeInTheDocument();
  expect(within(hero).getByText("Transport")).toBeInTheDocument();
  expect(
    screen.getByText(/Transport was the largest part of today's estimated footprint\./)
  ).toBeInTheDocument();

  const breakdown = screen.getByText("Breakdown of estimated emissions").closest("section");
  expect(within(breakdown).getByText("2.00 kg CO2e (67%)")).toBeInTheDocument();
  expect(within(breakdown).getByText("1.00 kg CO2e (33%)")).toBeInTheDocument();
  expect(within(breakdown).queryByText("Goods")).not.toBeInTheDocument();
  expect(
    within(breakdown).getByRole("img", { name: /Transport 2.00 kg CO2e, 67 percent/ })
  ).toBeInTheDocument();
});

test("uses stable tie messaging instead of implying a single category is larger", () => {
  render(
    <EmissionResult
      response={v2Response([
        includedDetail({ category: "transport", activity_type: "bus_ride", co2e: 1 }),
        includedDetail({ category: "energy", activity_type: "electricity_use", co2e: 1 }),
      ])}
    />
  );

  const hero = screen.getByText("Today's Estimated Footprint").closest("section");
  expect(within(hero).getByText("Multiple categories")).toBeInTheDocument();
  expect(
    screen.getByText(/Today's estimated footprint was spread across multiple categories\./)
  ).toBeInTheDocument();
});

test("shows a named-vehicle fallback assumption as an approximate estimate without codes", () => {
  render(
    <EmissionResult
      response={v2Response([
        includedDetail({
          raw_text: "I took a 5 km ride in a BMW X5.",
          category: "transport",
          activity_type: "car_ride",
          status: "fallback_estimated",
          source: "fallback",
          co2e: 1.1,
          confidence: { score: 0.55, level: "medium" },
          parameters: { vehicle_description: "BMW X5", distance: 5, distance_unit: "km" },
          assumptions: [
            {
              code: "vehicle.named.default_petrol_medium",
              message: "Recognized the supplied vehicle name BMW X5, but no verified class or fuel mapping is available; supplied medium petrol passenger-car parameters for the Climatiq estimate.",
            },
            {
              code: "fallback_factor.transport.road_distance",
              message: "Used local fallback factor generic road transport distance (0.18 kg CO2e/km) because no successful compatible Climatiq estimate was available.",
            },
          ],
          issues: [
            {
              code: "vehicle.named_model.unmapped",
              message: "No verified vehicle record matched this name.",
            },
          ],
        }),
      ])}
    />
  );

  const card = activityCard("Car Ride");
  expect(within(card).getByText("Approximate estimate")).toBeInTheDocument();
  expect(within(card).getByText(/Recognized the supplied vehicle name BMW X5/)).toHaveTextContent(
    "for this estimate"
  );
  expect(
    within(card).getByText(
      "Used an approximate emissions factor because a more specific estimate was not available."
    )
  ).toBeInTheDocument();
  expect(within(card).getByText(/Vehicle Description: BMW X5/)).toBeInTheDocument();
  expect(within(card).queryByText(/vehicle\.named/)).not.toBeInTheDocument();
  expect(within(card).queryByText("Local fallback")).not.toBeInTheDocument();
  expect(within(card).queryByText(/Climatiq/i)).not.toBeInTheDocument();
});

test("excludes unresolved activities from totals and the chart while showing Needs Attention", () => {
  render(
    <EmissionResult
      response={v2Response([
        includedDetail({ category: "energy", activity_type: "electricity_use", co2e: 2 }),
        unresolvedDetail(),
      ])}
    />
  );

  const hero = screen.getByText("Today's Estimated Footprint").closest("section");
  expect(within(hero).getByText("2.00 kg CO2e")).toBeInTheDocument();
  expect(within(hero).getByText("1 activity could not yet be included.")).toBeInTheDocument();
  const breakdown = screen.getByText("Breakdown of estimated emissions").closest("section");
  expect(within(breakdown).queryByText("Transport")).not.toBeInTheDocument();
  expect(
    within(breakdown).getByText("Activities needing attention are not included in this breakdown.")
  ).toBeInTheDocument();

  const needsAttention = screen.getByText("Needs Attention").closest("section");
  expect(within(needsAttention).getByText('"I used an electric scooter for 4 km."')).toBeInTheDocument();
  expect(within(needsAttention).getByText("We could not estimate this activity yet.")).toBeInTheDocument();
  expect(within(needsAttention).queryByText(/0\.00 kg CO2e/)).not.toBeInTheDocument();
  expect(
    screen.getByText(/1 activity could not yet be included in the estimate\./)
  ).toBeInTheDocument();
});

test("shows not-estimated activities separately without adding them to totals or breakdown", () => {
  render(
    <EmissionResult
      response={v2Response([
        includedDetail({ category: "energy", activity_type: "electricity_use", co2e: 1 }),
        {
          raw_text: "I walked 2 km.",
          category: "transport",
          activity_type: "walking",
          status: "not_estimated",
          co2e: 25,
          unit: "kg",
          source: "none",
          confidence: { score: 0.9, level: "high" },
          parameters: { distance: 2, distance_unit: "km" },
        },
      ])}
    />
  );

  const hero = screen.getByText("Today's Estimated Footprint").closest("section");
  expect(within(hero).getByText("1.00 kg CO2e")).toBeInTheDocument();
  const notIncluded = screen.getByText("Not Included in Estimated Emissions").closest("section");
  expect(within(notIncluded).getByText("Walking")).toBeInTheDocument();
  expect(
    within(notIncluded).getByText(
      "This activity was recognised but is not included in estimated emissions."
    )
  ).toBeInTheDocument();
  const breakdown = screen.getByText("Breakdown of estimated emissions").closest("section");
  expect(within(breakdown).queryByText("Transport")).not.toBeInTheDocument();
  expect(screen.queryByText("Needs Attention")).not.toBeInTheDocument();
});

test("handles all-unresolved and empty-detail responses without an empty chart or main driver", () => {
  const { rerender } = render(<EmissionResult response={v2Response([unresolvedDetail()])} />);

  let hero = screen.getByText("Today's Estimated Footprint").closest("section");
  expect(within(hero).getByText("No emissions estimate is available yet.")).toBeInTheDocument();
  expect(within(hero).queryByText("Main driver")).not.toBeInTheDocument();
  expect(screen.getByText("No estimated emissions to break down yet.")).toBeInTheDocument();

  rerender(<EmissionResult response={v2Response([])} />);
  hero = screen.getByText("Today's Estimated Footprint").closest("section");
  expect(within(hero).getByText("No emissions estimate is available yet.")).toBeInTheDocument();
  expect(screen.getByText("No carbon-relevant activities were found in this entry.")).toBeInTheDocument();
  expect(screen.queryByText("Needs Attention")).not.toBeInTheDocument();
});

test("keeps Ticket 6 confidence and factor evidence in a collapsed developer accordion", () => {
  render(
    <EmissionResult
      response={v2Response([
        includedDetail({
          raw_text: "I drove my electric car for 10 km.",
          category: "transport",
          activity_type: "car_ride",
          co2e: 1.14,
          confidence: { score: 0.75, level: "medium" },
          parameter_confidence: { score: 0.95, level: "high" },
          factor_confidence: { score: 0.75, level: "medium" },
          source_confidence: { score: 1, level: "high" },
          parameters: { distance: 10, distance_unit: "km", fuel_type: "electric" },
          factor: {
            activity_id: "fixture.electric.car",
            name: "Electric passenger car",
            score: 0.75,
            match_reasons: ["normalized fuel_type matched: electric"],
          },
        }),
      ])}
    />
  );

  const card = activityCard("Car Ride");
  expect(within(card).queryByText("Factor confidence")).not.toBeInTheDocument();
  expect(within(card).queryByText("Factor fit")).not.toBeInTheDocument();
  expect(within(card).queryByText("fixture.electric.car")).not.toBeInTheDocument();

  const accordion = screen.getByTestId("developer-details");
  expect(accordion).not.toHaveAttribute("open");

  fireEvent.click(within(accordion).getByText("How this estimate was calculated"));

  expect(accordion).toHaveAttribute("open");
  expect(within(accordion).getByText("Factor confidence")).toBeVisible();
  expect(within(accordion).getByText("Factor fit:")).toBeVisible();
  expect(within(accordion).getByText("Estimate confidence")).toBeVisible();
  expect(within(accordion).getByText("fixture.electric.car")).toBeVisible();
  expect(within(accordion).getByText("normalized fuel_type matched: electric")).toBeVisible();
  expect(within(accordion).queryByText(/accuracy/i)).not.toBeInTheDocument();
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

function v2Response(details, confidence = { score: 0.7, level: "medium" }) {
  const included = details.filter((detail) =>
    ["estimated", "fallback_estimated"].includes(detail.status)
  );
  return {
    version: "v2",
    total: {
      co2e: included.reduce((total, detail) => total + Number(detail.co2e || 0), 0),
      unit: "kg",
      confidence,
      source_breakdown: {},
    },
    details,
  };
}

function includedDetail(overrides = {}) {
  return {
    raw_text: "I used an activity.",
    category: "energy",
    activity_type: "electricity_use",
    status: "estimated",
    co2e: 1,
    unit: "kg",
    source: "climatiq",
    confidence: { score: 0.7, level: "medium" },
    parameter_confidence: { score: 0.8, level: "high" },
    factor_confidence: { score: 0.7, level: "medium" },
    source_confidence: { score: 1, level: "high" },
    parameters: {},
    assumptions: [],
    issues: [],
    ...overrides,
  };
}

function unresolvedDetail() {
  return {
    raw_text: "I used an electric scooter for 4 km.",
    category: "transport",
    activity_type: "generic_transport",
    status: "unresolved",
    co2e: 9,
    unit: "kg",
    source: "unresolved",
    confidence: { score: 0.2, level: "low" },
    parameters: {},
    assumptions: [],
    issues: [
      {
        code: "transport.unsupported_mode",
        message: "No compatible factor pathway has been implemented.",
      },
    ],
  };
}

function activityCard(name) {
  const activities = screen.getByText("Estimated Activities").closest("section");
  return within(activities).getByRole("heading", { name }).closest("article");
}
