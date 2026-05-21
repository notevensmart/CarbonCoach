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
    const apiBaseUrl = process.env.REACT_APP_API_BASE_URL || "";
    const res = await fetch(`${apiBaseUrl}/api/estimate`, {
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

    setEmissions({
     co2e: data.result.co2e,
     unit: data.result.unit,
     summary: data.result.summary,
     details: data.result.details,
    }); 
  } catch (err) {
    console.error(err);
    setError(err.message || "Failed to estimate emissions. Please try again.");
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

      {emissions && emissions.co2e !== null && (
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
                {d.status === "ok" || d.status === "fallback"
                    ? `${d.co2e.toFixed(2)} ${d.unit} CO2e (${d.source})`
                    : d.error_message}
                {d.parameters && (
                  <span className="text-gray-500">
                    {" "}using {Object.entries(d.parameters).map(([key, value]) => `${key}: ${value}`).join(", ")}
                  </span>
                )}
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
