import { useState } from "react";
import { Activity, Database } from "lucide-react";
import Operations from "./Operations";
import Sources from "./Sources";

const tabs = [
  { id: "operations", label: "Operations", icon: Activity },
  { id: "sources", label: "Sources", icon: Database },
] as const;

type TabId = (typeof tabs)[number]["id"];

export default function Admin() {
  const [active, setActive] = useState<TabId>("operations");

  return (
    <div className="space-y-6">
      {/* Tab bar */}
      <div className="flex gap-1 border-b border-slate-700/60 pb-px">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActive(id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors ${
              active === id
                ? "bg-slate-800 text-white border-b-2 border-indigo-500"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {active === "operations" && <Operations />}
      {active === "sources" && <Sources />}
    </div>
  );
}
