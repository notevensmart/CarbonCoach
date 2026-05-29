import React from "react";

const TAB_TONES = {
  overview: {
    selected: "border-teal-700 bg-teal-700 text-white shadow-teal-900/20",
    idle: "border-teal-200 bg-teal-50 text-teal-950 hover:bg-teal-100",
    focus: "focus-visible:outline-teal-700",
  },
  activities: {
    selected: "border-emerald-700 bg-emerald-700 text-white shadow-emerald-900/20",
    idle: "border-emerald-200 bg-emerald-50 text-emerald-950 hover:bg-emerald-100",
    focus: "focus-visible:outline-emerald-700",
  },
  details: {
    selected: "border-sky-700 bg-sky-700 text-white shadow-sky-900/20",
    idle: "border-sky-200 bg-sky-50 text-sky-950 hover:bg-sky-100",
    focus: "focus-visible:outline-sky-700",
  },
};

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
      className="flex w-full gap-2 rounded-2xl border border-stone-200 bg-white p-1.5 shadow-sm"
      onKeyDown={handleKeyDown}
      role="tablist"
    >
      {tabs.map((tab) => {
        const selected = tab.id === activeTab;
        const tone = TAB_TONES[tab.id] || TAB_TONES.overview;
        return (
          <button
            aria-controls={`result-panel-${tab.id}`}
            aria-selected={selected}
            className={`min-h-11 flex-1 cursor-pointer rounded-xl border px-3 py-2 text-sm font-semibold shadow-sm transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${
              tone.focus
            } ${
              selected
                ? `${tone.selected} shadow-md`
                : `${tone.idle} hover:shadow`
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
