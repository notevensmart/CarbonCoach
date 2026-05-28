import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import "@testing-library/jest-dom";

import EmissionResult from "./EmissionResult";
import Home from "../pages/Home";

test("renders result tabs and supports click and keyboard navigation", () => {
  render(<EmissionResult response={v2Response([includedDetail()])} />);

  const overviewTab = screen.getByRole("tab", { name: "Overview" });
  const activitiesTab = screen.getByRole("tab", { name: "Activities" });
  const detailsTab = screen.getByRole("tab", { name: "Details" });
  expect(overviewTab).toHaveAttribute("aria-selected", "true");

  fireEvent.click(activitiesTab);
  expect(activitiesTab).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText("Estimated Activities")).toBeVisible();

  fireEvent.keyDown(screen.getByRole("tablist", { name: "Result views" }), {
    key: "ArrowRight",
  });
  expect(detailsTab).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText("How this estimate was calculated")).toBeVisible();
});

test("uses backend coverage and explains estimate quality in human terms", () => {
  render(
    <EmissionResult
      response={v2Response(
        [
          includedDetail({
            status: "fallback_estimated",
            source: "fallback",
            assumptions: [
              {
                code: "fallback_factor.energy",
                message: "Used local fallback factor for electricity.",
              },
            ],
          }),
          unresolvedDetail(),
          notEstimatedDetail(),
        ],
        { score: 0.62, level: "medium" },
        null,
        {
          represented_activity_count: 9,
          included_in_total_count: 3,
          unresolved_count: 2,
          failed_count: 1,
          not_estimated_count: 2,
          estimate_is_partial: true,
        }
      )}
    />
  );

  expect(screen.getByText("We found 9 activities")).toBeInTheDocument();
  expect(screen.getByText("Backend coverage")).toBeInTheDocument();
  expect(screen.getByText("Estimate quality")).toBeInTheDocument();
  expect(screen.getAllByText("Medium").length).toBeGreaterThan(0);
  expect(screen.getByText("1 activity used assumptions")).toBeInTheDocument();
  expect(screen.getByText("1 activity is an approximate estimate")).toBeInTheDocument();
  expect(screen.getByText("3 activities need more detail")).toBeInTheDocument();
  expect(screen.getByText("The represented estimate is partial")).toBeInTheDocument();
});

test("shows category command center in stable category order with included totals only", () => {
  render(
    <EmissionResult
      response={v2Response([
        includedDetail({ category: "transport", activity_type: "car_ride", co2e: 2 }),
        includedDetail({ category: "energy", activity_type: "electricity_use", co2e: 1 }),
        unresolvedDetail({ category: "goods_services", activity_type: "generic_purchase" }),
        notEstimatedDetail({ category: "waste", activity_type: "composting" }),
      ])}
    />
  );

  const command = screen.getByText("Category command center").closest("section");
  expect(within(command).getByRole("img", { name: /Transport 2.00 kg CO2e, 67 percent/ }))
    .toBeInTheDocument();
  expect(
    within(command)
      .getAllByRole("heading", { level: 3 })
      .map((heading) => heading.textContent)
  ).toEqual(["Transport", "Energy", "Goods", "Waste"]);
  expect(within(command).getByText("2.00 kg")).toBeInTheDocument();
  expect(within(command).getByText("1.00 kg")).toBeInTheDocument();
  expect(within(command).getAllByText("0.00 kg")).toHaveLength(2);
});

test("handles zero-total and unresolved-only responses without implying completeness", () => {
  render(<EmissionResult response={v2Response([unresolvedDetail()])} />);

  const hero = screen.getByText("Today's Estimated Footprint").closest("section");
  expect(within(hero).getByText("No emissions estimate is available yet.")).toBeInTheDocument();
  expect(screen.getByText("No estimated emissions to break down yet.")).toBeInTheDocument();
  expect(screen.getByText(/This is a partial estimated footprint/)).toBeInTheDocument();
  expect(screen.queryByLabelText("Impact comparison")).not.toBeInTheDocument();
});

test("derives next-best clarification as guidance only when no clarification API is wired", () => {
  render(<EmissionResult response={v2Response([unresolvedDetail()])} />);

  expect(screen.getByText("Next best clarification")).toBeInTheDocument();
  expect(screen.getByText("How far was this trip?")).toBeInTheDocument();
  expect(screen.getByText(/guidance only for now\./)).toBeInTheDocument();
});

test("demo example chips populate the journal without creating fake results", () => {
  render(<Home />);

  fireEvent.click(screen.getByRole("button", { name: "Food + Waste" }));
  expect(screen.getByLabelText("Daily journal entry")).toHaveValue(
    "I bought coffee for $6, picked up groceries for $45, and threw away 500 g of plastic packaging."
  );
  expect(screen.queryByLabelText("Emission estimate results")).not.toBeInTheDocument();
});

test("Activities tab preserves estimated, needs-attention, and not-included activity surfaces", () => {
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
          parameters: { vehicle_description: "BMW X5", distance: 5, distance_unit: "km" },
          assumptions: [
            {
              code: "vehicle.named.default_petrol_medium",
              message:
                "Recognized the supplied vehicle name BMW X5, but no verified class or fuel mapping is available; supplied medium petrol passenger-car parameters for the Climatiq estimate.",
            },
          ],
          issues: [
            {
              code: "vehicle.named_model.unmapped",
              message: "No verified vehicle record matched this name.",
            },
          ],
        }),
        unresolvedDetail(),
        notEstimatedDetail(),
      ])}
    />
  );

  fireEvent.click(screen.getByRole("tab", { name: "Activities" }));
  const activities = screen.getByRole("tabpanel", { name: "Activities" });
  const card = within(activities).getByRole("heading", { name: "Car Ride" }).closest("article");

  expect(within(card).getByText("Approximate estimate")).toBeInTheDocument();
  expect(within(card).getByText("What we assumed")).toBeInTheDocument();
  expect(within(card).getByText(/Recognized the supplied vehicle name BMW X5/)).toHaveTextContent(
    "for this estimate"
  );
  expect(within(card).queryByText(/vehicle\.named/)).not.toBeInTheDocument();
  expect(within(activities).getByText("Needs Attention")).toBeInTheDocument();
  expect(within(activities).getByText("We could not estimate this activity yet.")).toBeInTheDocument();
  expect(within(activities).getByText("Not Included in Estimated Emissions")).toBeInTheDocument();
  expect(
    within(activities).getByText(
      "This activity was recognised but is not included in estimated emissions."
    )
  ).toBeInTheDocument();
});

test("Details tab exposes confidence, factor diagnostics, raw JSON, and suppressed comparison metadata", () => {
  render(
    <EmissionResult
      response={v2Response(
        [
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
            factor_diagnostics: {
              intent_key: "transport.car.distance",
              search_query: "electric passenger car distance",
              selector_filters: { category: "transport", unit_type: "Distance" },
              candidate_count: 3,
              selected_activity_id: "fixture.electric.car",
              selected_reason: "Best compatible electric factor.",
              fallback_used: true,
              fallback_reason: "Climatiq unavailable",
              fallback_assumption_code: "fallback_factor.transport.road_distance",
              top_rejections: [
                { activity_id: "fixture.petrol.car", reason: "fuel_type mismatch" },
              ],
            },
          }),
        ],
        { score: 0.75, level: "medium" },
        comparisonFixture(),
        {
          represented_activity_count: 2,
          included_in_total_count: 1,
          unresolved_count: 1,
          failed_count: 0,
          not_estimated_count: 0,
          estimate_is_partial: true,
        }
      )}
    />
  );

  expect(screen.queryByLabelText("Impact comparison")).not.toBeInTheDocument();
  const overview = screen.getByRole("tabpanel", { name: "Overview" });
  expect(within(overview).queryByText("fixture.electric.car")).not.toBeInTheDocument();
  expect(within(overview).queryByText("transport.car.distance")).not.toBeInTheDocument();

  fireEvent.click(screen.getByRole("tab", { name: "Details" }));
  const details = screen.getByTestId("developer-details");
  expect(within(details).getByText("Total estimate confidence")).toBeVisible();
  expect(within(details).getByText("Parameter confidence")).not.toBeVisible();

  fireEvent.click(within(details).getByText("Per-Activity Details"));
  fireEvent.click(within(details).getAllByText("Car Ride")[0]);
  expect(within(details).getByText("Parameter confidence")).toBeVisible();
  expect(within(details).getByText("Factor confidence")).toBeVisible();
  expect(within(details).getByText("Estimate confidence")).toBeVisible();

  fireEvent.click(within(details).getByText("Factor Linking"));
  expect(within(details).getAllByText("fixture.electric.car")[0]).toBeVisible();
  expect(within(details).getAllByText("transport.car.distance")[0]).toBeVisible();
  expect(within(details).getByText("Candidate count")).toBeVisible();
  expect(within(details).getByText("Climatiq unavailable")).toBeVisible();
  expect(within(details).getByText("fixture.petrol.car:")).toBeVisible();
  expect(within(details).getByText("normalized fuel_type matched: electric")).toBeVisible();
  expect(within(details).queryByText(/accuracy/i)).not.toBeInTheDocument();

  fireEvent.click(within(details).getByText("Impact Comparison"));
  expect(within(details).getByText("Impact comparison calculation")).toBeVisible();
  expect(within(details).getByText("average_petrol_car_distance")).toBeVisible();
  expect(
    within(details).getByText(/not shown in the primary result because the current display rules/)
  ).toBeVisible();

  fireEvent.click(within(details).getByText("Raw JSON Preview"));
  expect(
    within(details).getByText((content, node) => {
      return node.tagName.toLowerCase() === "pre" && content.includes('"version": "v2"');
    })
  ).toBeVisible();
});

test("Details tab degrades gracefully when optional diagnostics are absent", () => {
  render(<EmissionResult response={v2Response([includedDetail()])} />);

  fireEvent.click(screen.getByRole("tab", { name: "Details" }));
  fireEvent.click(screen.getByText("Factor Linking"));
  expect(
    screen.getByText("No factor linking diagnostics were supplied for this response.")
  ).toBeVisible();
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

function v2Response(
  details,
  confidence = { score: 0.7, level: "medium" },
  comparison = null,
  coverage = null,
  overrides = {}
) {
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
    coverage,
    comparison,
    details,
    ...overrides,
  };
}

function comparisonFixture(overrides = {}) {
  return {
    key: "average_petrol_car_distance",
    message: "Roughly equivalent to driving an average petrol car for 16 km.",
    amount: 16,
    unit: "km",
    reference_label: "average petrol passenger car",
    kg_co2e_per_unit: 0.192,
    input_total_kg_co2e: 3.072,
    applicability: "Australia; representative petrol passenger-car operational travel emissions only.",
    source_note:
      "Maintained Australian approximate reference from National Greenhouse Accounts Factors 2025.",
    approximate: true,
    ...overrides,
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

function unresolvedDetail(overrides = {}) {
  return {
    raw_text: "I took a trip across town.",
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
        code: "transport.missing_distance",
        message: "Distance is required for this transport estimate.",
      },
    ],
    ...overrides,
  };
}

function notEstimatedDetail(overrides = {}) {
  return {
    raw_text: "I walked 2 km.",
    category: "transport",
    activity_type: "walking",
    status: "not_estimated",
    co2e: 25,
    unit: "kg",
    source: "none",
    confidence: { score: 0.9, level: "high" },
    parameters: { distance: 2, distance_unit: "km" },
    assumptions: [],
    issues: [],
    ...overrides,
  };
}
