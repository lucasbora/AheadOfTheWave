import React from "react";
import { gradeColor, gradeFromScore, fmt } from "../lib/grade";
import ScoreBar from "./ScoreBar";

const BREAKDOWN_KEYS = [
  { key: "physical_risk", label: "Physical Risk" },
  { key: "regulatory_risk", label: "Regulatory Risk" },
  { key: "compliance", label: "Compliance" },
  { key: "ead", label: "EAD" },
];

export const InvestmentGradeCard = ({ data, loading }) => {
  const score = data?.score ?? null;
  const grade = data?.grade ?? gradeFromScore(score);
  const label = data?.label || data?.grade_label || "—";
  const color = gradeColor(grade);
  const breakdown = data?.breakdown || data?.scores || {};

  return (
    <div className="panel panel-in" data-testid="investment-grade-card">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1E2535]">
        <div>
          <div className="label-overline">INVESTMENT GRADE</div>
          <div className="text-[13px] mt-0.5">Composite Water Risk Score</div>
        </div>
        <span className="mono text-[10px] text-[#5C667A] uppercase tracking-[0.14em]">
          /100
        </span>
      </div>

      <div className="grid grid-cols-[1fr_auto] gap-4 p-5 items-center border-b border-[#1E2535]">
        <div>
          <div
            className={`mono font-semibold leading-none grade-glow-${grade?.toString().toLowerCase().replace("+", "plus")}`}
            style={{ color, fontSize: 96, letterSpacing: "-0.04em" }}
            data-testid="grade-letter"
          >
            {loading ? "··" : grade || "—"}
          </div>
          <div className="mt-3">
            <span
              className="mono text-[11px] tracking-wider uppercase px-2 py-0.5"
              style={{
                color,
                background: `${color}1A`,
                border: `1px solid ${color}55`,
              }}
              data-testid="grade-label"
            >
              {label}
            </span>
          </div>
        </div>
        <div className="text-right">
          <div
            className="mono leading-none"
            style={{ color, fontSize: 38, letterSpacing: "-0.02em" }}
            data-testid="score-numeric"
          >
            {loading ? "—" : fmt(score, 2)}
          </div>
          <div className="mono text-[10px] text-[#5C667A] uppercase tracking-[0.14em] mt-2">
            of 100.00
          </div>
        </div>
      </div>

      <div className="p-4 space-y-3">
        <div className="label-overline">RISK BREAKDOWN</div>
        {BREAKDOWN_KEYS.map((b) => {
          const v = Number(breakdown?.[b.key] ?? 0);
          return (
            <div key={b.key} data-testid={`breakdown-${b.key}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[12px] text-[#8B95A5]">{b.label}</span>
                <span className="mono text-[11px] text-white">
                  {fmt(v, 1)}
                  <span className="text-[#5C667A]"> / 100</span>
                </span>
              </div>
              <ScoreBar value={v} grade={gradeFromScore(v)} height={4} />
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default InvestmentGradeCard;
