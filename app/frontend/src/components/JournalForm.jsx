import { useState } from "react";

export default function JournalForm({ onSubmit }) {
  const [input, setInput] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSubmit(input.trim());
    setInput("");
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <label className="text-lg font-medium flex items-center gap-2">
        🌿 What did you do today?
      </label>
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        rows={4}
        placeholder="e.g., Took a 5km bus ride, cooked dinner at home..."
        className="p-3 border border-gray-300 rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-green-500"
      />
      <button
        type="submit"
        className="self-start bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 transition"
      >
        Estimate Emissions
      </button>
    </form>
  );
}
