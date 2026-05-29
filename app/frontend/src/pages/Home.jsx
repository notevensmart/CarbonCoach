import React, { useState } from "react";
import EmissionResult from "../components/EmissionResult";
import DemoExampleChips from "../components/results/DemoExampleChips";

const DEFAULT_ENDPOINT = "/api/estimate-v2";

const Home = () => {
  const [entry, setEntry] = useState("");
  const [emissions, setEmissions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event?.preventDefault();
    if (!entry.trim()) {
      setError("Add a journal entry before estimating.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const apiBaseUrl = process.env.REACT_APP_API_BASE_URL || "";
      const endpoint = process.env.REACT_APP_ESTIMATE_ENDPOINT || DEFAULT_ENDPOINT;
      const res = await fetch(`${apiBaseUrl}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ journal: entry.trim() }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Server error");
      }

      setEmissions(data);
    } catch (err) {
      console.error(err);
      setError(err.message || "Failed to estimate emissions. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleEntryChange = (value) => {
    setEntry(value);
    setError("");
    if (emissions) {
      setEmissions(null);
    }
  };

  return (
    <main className="min-h-screen bg-[#f6f7f2] px-4 py-6 text-stone-950 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-6">
          <p className="text-sm font-semibold uppercase tracking-wide text-teal-700">
            Single-session reflection
          </p>
          <h1 className="mt-2 text-4xl font-bold tracking-tight text-teal-950 sm:text-5xl">
            CarbonCoach
          </h1>
        </header>

        <section
          aria-labelledby="journal-entry-title"
          className="rounded-3xl border border-teal-100 bg-white p-5 shadow-sm shadow-teal-900/5 sm:p-6"
        >
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 id="journal-entry-title" className="text-xl font-semibold text-stone-950">
                Turn your day into a transparent carbon estimate.
              </h2>
              <p className="mt-1 text-sm text-stone-600">
                Write a normal daily entry. CarbonCoach extracts the activities, estimates CO2e,
                and shows what was counted, assumed, and left unresolved.
              </p>
            </div>
          </div>

          <form className="mt-5" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor="journal-entry">
              Daily journal entry
            </label>
            <textarea
              className="h-36 w-full resize-y rounded-2xl border border-stone-300 bg-stone-50 p-4 text-base text-stone-950 shadow-inner outline-none transition-colors duration-200 placeholder:text-stone-400 focus:border-teal-700 focus:bg-white focus:ring-2 focus:ring-teal-700/20"
              id="journal-entry"
              onChange={(event) => handleEntryChange(event.target.value)}
              placeholder="What did you do today? e.g., Used a 2 kW heater for 3 hours, drove 7k, and recycled 500g of plastic..."
              value={entry}
            />

            <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <DemoExampleChips onSelect={handleEntryChange} />
              <button
                className="min-h-11 cursor-pointer rounded-xl bg-teal-800 px-5 py-3 font-semibold text-white shadow-sm transition-colors duration-200 hover:bg-teal-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 disabled:cursor-not-allowed disabled:bg-stone-400"
                disabled={loading}
                type="submit"
              >
                {loading ? "Estimating..." : "Estimate Emissions"}
              </button>
            </div>
          </form>
        </section>

        <div aria-live="polite">{emissions && <EmissionResult response={emissions} />}</div>

        {error && (
          <div
            className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 font-semibold text-red-700"
            role="alert"
          >
            {error}
          </div>
        )}
      </div>
    </main>
  );
};

export default Home;
