import React, { useState } from "react";
import { ChevronDown, ChevronRight, Check, X } from "lucide-react";
import FeasibilityPill from "./FeasibilityPill";
import EvidenceTag from "./EvidenceTag";
import ConfidenceBadge from "./ConfidenceBadge";

const IMPACT_COLORS = {
  HIGH: "#FF3B30",
  MED: "#FF9F0A",
  MEDIUM: "#FF9F0A",
  LOW: "#30D158",
};

const PRI_COLORS = {
  P0: "#FF3B30",
  HIGH: "#FF3B30",
  P1: "#FF9F0A",
  MED: "#FF9F0A",
  MEDIUM: "#FF9F0A",
  P2: "#00C2FF",
  LOW: "#00C2FF",
};

function ImpactBadge({ impact }) {
  const v = (impact || "MED").toString().toUpperCase();
  const color = IMPACT_COLORS[v] || "#8B95A5";
  return (
    <span
      className="mono text-[10px] tracking-wider px-1.5 py-0.5"
      style={{ color, background: `${color}1A`, border: `1px solid ${color}55` }}
    >
      {v}
    </span>
  );
}

function PriorityBadge({ p }) {
  const v = (p || "MED").toString().toUpperCase();
  const color = PRI_COLORS[v] || "#8B95A5";
  return (
    <span
      className="mono text-[10px] tracking-wider px-1.5 py-0.5"
      style={{ color, background: `${color}1A`, border: `1px solid ${color}55` }}
    >
      {v}
    </span>
  );
}

export const ClaudeAuditPanel = ({ data, loading }) => {
  const [openClaim, setOpenClaim] = useState(-1);

  const feasibility = data?.feasibility || {};
  const overall = data?.overall || data?.assessment || {};
  const topRisks = data?.top_risks || data?.risks || [];
  const claims = data?.supported_claims || data?.claims || [];
  const dataGaps = data?.data_gaps || data?.gaps || [];
  const nextChecks = data?.next_checks || data?.recommended_checks || [];
  const consistency = data?.consistency_checks || data?.consistency || {};

  return (
    <div className="panel panel-in" data-testid="claude-audit-panel">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1E2535]">
        <div className="flex items-center gap-3">
          <div>
            <div className="label-overline">CLAUDE · AUDIT</div>
            <div className="text-[13px] mt-0.5">
              Feasibility & Evidence Trace
            </div>
          </div>
        </div>
        {loading && (
          <span className="mono text-[10px] text-[#FF9F0A]">…analysing</span>
        )}
      </div>

      {/* Feasibility pills */}
      <div className="grid grid-cols-3 gap-2 p-4 border-b border-[#1E2535]">
        <FeasibilityPill
          kind="WATER"
          status={feasibility.water}
          testId="feas-water"
        />
        <FeasibilityPill
          kind="COOLING"
          status={feasibility.cooling}
          testId="feas-cooling"
        />
        <FeasibilityPill
          kind="PERMIT"
          status={feasibility.permit}
          testId="feas-permit"
        />
      </div>

      {/* Overall */}
      <div className="p-4 border-b border-[#1E2535]" data-testid="overall-assessment">
        <div className="flex items-center gap-2 mb-2">
          <span className="label-overline">OVERALL</span>
          {overall.status && (
            <span
              className="mono text-[10px] uppercase tracking-wider px-1.5 py-0.5"
              style={{
                color: "#00C2FF",
                background: "rgba(0,194,255,0.10)",
                border: "1px solid rgba(0,194,255,0.4)",
              }}
            >
              {overall.status}
            </span>
          )}
          {overall.confidence && (
            <ConfidenceBadge level={overall.confidence} />
          )}
        </div>
        <div className="text-[12.5px] text-white/90 leading-relaxed">
          {overall.reason || overall.summary || "—"}
        </div>
      </div>

      {/* Top risks */}
      <div className="p-4 border-b border-[#1E2535]">
        <div className="label-overline mb-2">TOP RISKS</div>
        <div className="space-y-2">
          {topRisks.length === 0 && (
            <div className="mono text-[11px] text-[#5C667A]">no risks reported</div>
          )}
          {topRisks.map((r, i) => (
            <div
              key={i}
              className="flex gap-2 p-2 border border-[#1E2535] bg-[#0A0E1A]"
              data-testid={`top-risk-${i}`}
            >
              <ImpactBadge impact={r.impact} />
              <div className="flex-1 min-w-0">
                <div className="text-[12px] text-white">
                  {r.text || r.description || r.risk || "—"}
                </div>
                {r.field_path && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {(Array.isArray(r.field_path) ? r.field_path : [r.field_path]).map(
                      (fp, j) => (
                        <EvidenceTag key={j}>{fp}</EvidenceTag>
                      )
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Supported claims accordion */}
      <div className="p-4 border-b border-[#1E2535]">
        <div className="label-overline mb-2">SUPPORTED CLAIMS</div>
        <div className="border border-[#1E2535] divide-y divide-[#1E2535]">
          {claims.length === 0 && (
            <div className="mono text-[11px] text-[#5C667A] p-2">none</div>
          )}
          {claims.map((c, i) => {
            const open = openClaim === i;
            return (
              <div key={i} data-testid={`claim-${i}`}>
                <button
                  onClick={() => setOpenClaim(open ? -1 : i)}
                  className="w-full flex items-start gap-2 p-2 text-left hover:bg-[#131A2B]"
                >
                  {open ? (
                    <ChevronDown size={14} className="mt-0.5 text-[#00C2FF]" />
                  ) : (
                    <ChevronRight size={14} className="mt-0.5 text-[#5C667A]" />
                  )}
                  <span className="flex-1 text-[12px] text-white">
                    {c.claim || c.text || `Claim #${i + 1}`}
                  </span>
                </button>
                {open && (
                  <div className="px-2 pb-3 pt-1 bg-[#0A0E1A]">
                    <div className="mono text-[10px] text-[#5C667A] uppercase tracking-wider mb-1.5">
                      EVIDENCE PATHS
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {(c.evidence || c.evidence_paths || []).map((e, j) => (
                        <EvidenceTag key={j}>{typeof e === "string" ? e : JSON.stringify(e)}</EvidenceTag>
                      ))}
                      {(!c.evidence || !c.evidence.length) && (
                        <span className="mono text-[10px] text-[#5C667A]">—</span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Data gaps */}
      <div className="p-4 border-b border-[#1E2535]">
        <div className="label-overline mb-2">DATA GAPS</div>
        <ul className="space-y-1">
          {dataGaps.length === 0 && (
            <li className="mono text-[11px] text-[#5C667A]">none</li>
          )}
          {dataGaps.map((g, i) => (
            <li
              key={i}
              className="text-[12px] text-[#FF9F0A] flex gap-2"
              data-testid={`gap-${i}`}
            >
              <span className="mono text-[10px] mt-0.5">▸</span>
              <span>{typeof g === "string" ? g : g.text || JSON.stringify(g)}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Next checks */}
      <div className="p-4 border-b border-[#1E2535]">
        <div className="label-overline mb-2">RECOMMENDED NEXT CHECKS</div>
        <div className="space-y-1.5">
          {nextChecks.length === 0 && (
            <div className="mono text-[11px] text-[#5C667A]">none</div>
          )}
          {nextChecks.map((n, i) => (
            <div
              key={i}
              className="flex items-start gap-2 p-2 bg-[#0A0E1A] border border-[#1E2535]"
              data-testid={`next-check-${i}`}
            >
              <PriorityBadge p={n.priority || n.p || "MED"} />
              <span className="text-[12px] text-white">
                {n.text || n.check || (typeof n === "string" ? n : JSON.stringify(n))}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Consistency checks */}
      <div className="p-4">
        <div className="label-overline mb-2">CONSISTENCY CHECKS</div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-1.5">
          {Object.keys(consistency).length === 0 && (
            <div className="mono text-[11px] text-[#5C667A] col-span-full">
              no checks
            </div>
          )}
          {Object.entries(consistency).map(([k, v]) => {
            const ok = v === true || v === "pass" || v === 1;
            return (
              <div
                key={k}
                className="flex items-center gap-2 px-2 py-1 border"
                style={{
                  borderColor: ok ? "rgba(48,209,88,0.45)" : "rgba(255,59,48,0.45)",
                  background: ok ? "rgba(48,209,88,0.08)" : "rgba(255,59,48,0.08)",
                }}
                data-testid={`consistency-${k}`}
              >
                {ok ? (
                  <Check size={12} color="#30D158" />
                ) : (
                  <X size={12} color="#FF3B30" />
                )}
                <span className="mono text-[10px] uppercase tracking-wider text-white truncate">
                  {k.replace(/_/g, " ")}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default ClaudeAuditPanel;
