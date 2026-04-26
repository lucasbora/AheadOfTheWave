import React from "react";
import RiskDots from "./RiskDots";
import { fmt } from "../lib/grade";

const CATS = [
  { key: "water_availability", label: "Water Availability" },
  { key: "drought", label: "Drought" },
  { key: "flooding", label: "Flooding" },
  { key: "water_quality", label: "Water Quality" },
];

function pickCategory(data, key, label) {
  const cats = data?.risk_categories || data?.categories || data?.risks || [];
  if (Array.isArray(cats)) {
    const found = cats.find((c) => {
      const n = (c.name || c.key || c.id || "").toString().toLowerCase().replace(/\s+/g, "_");
      return n === key || n.includes(key.split("_")[0]);
    });
    if (found) return found;
  }
  if (data?.[key]) return data[key];
  return null;
}

export const RiskBreakdownPanel = ({ data }) => {
  const fsi = data?.fsi ?? data?.flood_severity_index ?? null;
  const sat = data?.satellite || data?.metadata?.satellite || {};
  return (
    <div className="panel panel-in" data-testid="risk-breakdown-panel">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1E2535]">
        <div>
          <div className="label-overline">RISK BREAKDOWN</div>
          <div className="text-[13px] mt-0.5">Hydrological & Climate Stress</div>
        </div>
      </div>

      <div className="px-4 py-3 divide-y divide-[#1E2535]">
        {CATS.map((c) => {
          const cat = pickCategory(data, c.key, c.label);
          const score = Number(cat?.score_1_5 ?? cat?.score ?? cat?.level ?? 0);
          const pct = Number(cat?.contribution_pct ?? cat?.weight ?? cat?.contribution ?? 0);
          return (
            <div
              key={c.key}
              className="grid grid-cols-[1fr_auto_auto] items-center gap-4 py-3"
              data-testid={`risk-row-${c.key}`}
            >
              <span className="text-[12px] text-white">{c.label}</span>
              <RiskDots value={score} testId={`risk-dots-${c.key}`} />
              <span className="mono text-[11px] text-[#8B95A5] tabular-nums w-14 text-right">
                {fmt(pct, 1)}%
              </span>
            </div>
          );
        })}
      </div>

      {/* FSI Gauge */}
      <div className="px-4 pb-4">
        <div className="flex items-center justify-between mb-1.5">
          <span className="label-overline">
            FSI · Flood Severity Index
          </span>
          <span className="mono text-[11px] text-white">
            {fsi == null ? "—" : Number(fsi).toFixed(3)}
            <span className="text-[#5C667A]"> / 1.000</span>
          </span>
        </div>
        <div className="gauge-track">
          <div
            className="gauge-fill bar-fill"
            style={{
              width: `${Math.max(0, Math.min(1, Number(fsi) || 0)) * 100}%`,
              background:
                Number(fsi) > 0.66
                  ? "#FF3B30"
                  : Number(fsi) > 0.33
                    ? "#FF9F0A"
                    : "#30D158",
            }}
          />
        </div>
        <div className="flex justify-between mono text-[9px] text-[#5C667A] mt-1">
          <span>0.0 · safe</span>
          <span>0.5</span>
          <span>1.0 · critical</span>
        </div>
      </div>

      {/* Satellite metadata strip */}
      <div className="border-t border-[#1E2535] px-4 py-2.5 flex flex-wrap items-center gap-3 bg-[#0A0E1A]">
        <span className="label-overline">SAT META</span>
        <span className="mono text-[10px] text-[#8B95A5]">
          tile <span className="text-white">{sat.tile_id || "—"}</span>
        </span>
        <span className="mono text-[10px] text-[#8B95A5]">
          acq <span className="text-white">{sat.acquisition_date || "—"}</span>
        </span>
        <span className="mono text-[10px] text-[#8B95A5]">
          cloud{" "}
          <span className="text-white">
            {sat.cloud_cover != null ? `${sat.cloud_cover}%` : "—"}
          </span>
        </span>
        <span className="ml-auto mono text-[10px] text-[#00C2FF] px-2 py-0.5 border border-[#00C2FF]/40 bg-[#00C2FF]/10">
          {sat.source || "ESA Copernicus"}
        </span>
      </div>
    </div>
  );
};

export default RiskBreakdownPanel;
