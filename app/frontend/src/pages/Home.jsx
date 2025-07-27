import React, { useState } from "react";

const Home = () => {
  const [entry, setEntry] = useState("");
  const [emissions, setEmissions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

const handleSubmit = async () => {
  setLoading(true);
  setError("");

  try {
    const res = await fetch("https://carboncoach-518373042997.us-central1.run.app/process", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({ journal_entry: entry }),
    });

    if (!res.ok) {
      throw new Error("Server error");
    }

    const data = await res.json(); // Because FastAPI returns JSON
    setEmissions({
     co2e: data.result.co2e,
     unit: data.result.unit,
     summary: data.result.summary,
     details: data.result.details,
    }); 
  } catch (err) {
    console.error(err);
    setError("Failed to estimate emissions. Please try again.");
  } finally {
    setLoading(false);
  }
};

  return (
    <div className="p-6 bg-gray-100 min-h-screen">
      <h1 className="text-4xl font-bold text-green-700 mb-6 flex items-center gap-2">
        CarbonCoach <span>🌱</span>
      </h1>

      <div className="mb-4 flex items-center gap-2">
        <span role="img" aria-label="leaf">🌿</span>
        <h2 className="text-xl font-semibold">What did you do today?</h2>
      </div>

      <textarea
        className="w-full h-32 p-4 mb-4 border rounded-md shadow-sm"
        placeholder="e.g., Took a 5km bus ride, cooked dinner at home..."
        value={entry}
        onChange={(e) => setEntry(e.target.value)}
      />

      <button
        onClick={handleSubmit}
        disabled={loading}
        className="bg-green-600 hover:bg-green-700 text-white font-semibold py-2 px-4 rounded"
      >
        {loading ? "Estimating..." : "Estimate Emissions"}
      </button>

      {emissions && emissions.co2e && (
        <div className="mt-6 p-4 bg-white rounded-md shadow-md">
            <p className="text-lg">
            ✅ <strong>Estimated Emissions:</strong>{" "}
            <span className="text-green-700 font-bold">
                {emissions.co2e.toFixed(2)} {emissions.unit}
            </span>
            </p>
            <p className="mt-2 text-sm text-gray-600">{emissions.summary}</p>

            <ul className="mt-4 list-disc list-inside">
            {emissions.details.map((d, idx) => (
                <li key={idx}>
                <strong>{d.label}</strong> ({d.category}) →{" "}
                {d.status === "ok"
                    ? `${d.co2e.toFixed(2)} ${d.unit} CO2e`
                    : d.error_message}
                </li>
            ))}
            </ul>
        </div>
      )}

      {error && (
        <div className="mt-4 text-red-600 font-semibold">{error}</div>
      )}
    </div>
  );
};

export default Home;
