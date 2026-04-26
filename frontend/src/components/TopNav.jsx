import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Settings, Waves } from "lucide-react";
import SettingsDialog from "./SettingsDialog";

const TABS = [
  { to: "/", label: "Dashboard", testId: "nav-dashboard" },
  { to: "/compare", label: "Compare", testId: "nav-compare" },
  { to: "/heatmap", label: "Heatmap", testId: "nav-heatmap" },
  { to: "/finland", label: "Finland Oracle", testId: "nav-finland" },
];

export const TopNav = () => {
  const loc = useLocation();
  const [open, setOpen] = useState(false);

  return (
    <header
      className="flex items-center justify-between border-b border-[#1E2535] bg-[#0A0E1A] sticky top-0 z-[1000]"
      data-testid="top-nav"
    >
      <div className="flex items-center">
        <Link
          to="/"
          className="flex items-center gap-2.5 px-5 py-3 border-r border-[#1E2535] hover:bg-[#131A2B] transition-colors"
          data-testid="logo-link"
        >
          <div
            className="flex items-center justify-center w-7 h-7"
            style={{ background: "#00C2FF", color: "#0A0E1A" }}
          >
            <Waves size={16} strokeWidth={2.5} />
          </div>
          <div className="leading-tight">
            <div className="text-[13px] font-medium tracking-tight">
              Ahead Of The Wave
            </div>
            <div className="mono text-[9px] uppercase tracking-[0.18em] text-[#5C667A]">
              Water Risk Intelligence
            </div>
          </div>
        </Link>
        <nav className="flex">
          {TABS.map((t) => {
            const active =
              t.to === "/"
                ? loc.pathname === "/"
                : loc.pathname.startsWith(t.to);
            return (
              <Link
                key={t.to}
                to={t.to}
                data-testid={t.testId}
                className={`tab-link ${active ? "active" : ""}`}
              >
                {t.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="flex items-center gap-3 px-4">
        <div className="mono text-[10px] uppercase tracking-[0.14em] text-[#5C667A] hidden md:block">
          v1.0 · TERMINAL
        </div>
        <span
          className="mono text-[10px] inline-flex items-center gap-1.5 px-2 py-1 border border-[#1E2535] text-[#30D158]"
          data-testid="live-indicator"
        >
          <span
            className="w-1.5 h-1.5 inline-block"
            style={{ background: "#30D158", boxShadow: "0 0 6px #30D158" }}
          />
          LIVE
        </span>
        <button
          data-testid="settings-button"
          onClick={() => setOpen(true)}
          className="p-2 border border-[#1E2535] hover:border-[#00C2FF] hover:text-[#00C2FF] text-[#8B95A5] transition-colors"
          aria-label="Settings"
        >
          <Settings size={14} />
        </button>
      </div>

      <SettingsDialog open={open} onOpenChange={setOpen} />
    </header>
  );
};

export default TopNav;
