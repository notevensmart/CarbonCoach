import React, { useState } from "react";
import EmissionResult from "../components/EmissionResult";

const DEFAULT_ENDPOINT = "/api/estimate-v2";

const Home = () => {
  const [entry, setEntry] = useState("");
  const [emissions, setEmissions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
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
        body: JSON.stringify({ journal: entry }),
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

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <h1 className="mb-6 text-4xl font-bold text-green-700">
        CarbonCoach
      </h1>

      <div className="mb-4">
        <h2 className="text-xl font-semibold">What did you do today?</h2>
      </div>

      <textarea
        className="mb-4 h-32 w-full rounded-md border p-4 shadow-sm"
        placeholder="e.g., Used a 2 kW heater for 3 hours..."
        value={entry}
        onChange={(event) => setEntry(event.target.value)}
      />

      <button
        onClick={handleSubmit}
        disabled={loading}
        className="rounded bg-green-600 px-4 py-2 font-semibold text-white hover:bg-green-700 disabled:cursor-not-allowed disabled:bg-gray-400"
      >
        {loading ? "Estimating..." : "Estimate Emissions"}
      </button>

      {emissions && <EmissionResult response={emissions} />}

      {error && (
        <div className="mt-4 font-semibold text-red-600">{error}</div>
      )}
    </div>
  );
};

export default Home;
