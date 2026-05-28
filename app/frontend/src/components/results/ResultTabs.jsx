import React from "react";

export default function ResultTabs({ tabs, activeTab, onChange }) {
  const handleKeyDown = (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      return;
    }

    event.preventDefault();
    const currentIndex = tabs.findIndex((tab) => tab.id === activeTab);
    let nextIndex = currentIndex;
    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % tabs.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = tabs.length - 1;
    }

    const nextTab = tabs[nextIndex];
    onChange(nextTab.id);
    requestAnimationFrame(() => {
      document.getElementById(`result-tab-${nextTab.id}`)?.focus();
    });
  };

  return (
    <div
      aria-label="Result views"
      className="flex w-full gap-1 rounded-xl border border-stone-200 bg-stone-100 p-1"
      onKeyDown={handleKeyDown}
      role="tablist"
    >
      {tabs.map((tab) => {
        const selected = tab.id === activeTab;
        return (
          <button
            aria-controls={`result-panel-${tab.id}`}
            aria-selected={selected}
            className={`min-h-11 flex-1 cursor-pointer rounded-lg px-3 py-2 text-sm font-semibold transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 ${
              selected
                ? "bg-white text-teal-950 shadow-sm"
                : "text-stone-700 hover:bg-white/70 hover:text-stone-950"
            }`}
            id={`result-tab-${tab.id}`}
            key={tab.id}
            onClick={() => onChange(tab.id)}
            role="tab"
            type="button"
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
