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
      const res = await fetch(`${import.meta.env.VITE_API_URL}/api/estimate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ journal: entry }),
      });

      if (!res.ok) {
        throw new Error("Server error");
      }

      const data = await res.json();
      setEmissions(data);
    } catch (err) {
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

      {emissions && (
        <div className="mt-6 p-4 bg-white rounded-md shadow-md">
          <p className="text-lg">
            ✅ <strong>Estimated Emissions:</strong>{" "}
            <span className="text-green-700 font-bold">
              {emissions.co2e.toFixed(2)} {emissions.unit}
            </span>
          </p>
        </div>
      )}

      {error && (
        <div className="mt-4 text-red-600 font-semibold">{error}</div>
      )}
    </div>
  );
};

export default Home;
