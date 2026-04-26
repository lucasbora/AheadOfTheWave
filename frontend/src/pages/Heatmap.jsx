import React, { useState } from "react";
import LeafletMap from "../components/LeafletMap";
import { ext, loadSettings } from "../lib/api";
import { gradeColor, gradeFromScore, fmt, fmtCoord } from "../lib/grade";
import { Square, X, Play } from "lucide-react";
import { toast } from "sonner";

const USER_TYPES = [
  "data_center",
  "industrial_park",
  "logistics",
  "residential_developer",
  "generic_investor",
];

const STEPS = [5, 10, 25];

export default function Heatmap() {
  const [userType, setUserType] = useState(loadSettings().defaultUserType);
  const [step, setStep] = useState(10);
  const [bbox, setBbox] = useState(null);
  const [points, setPoints] = useState([]);
  const [loading, setLoading] = useState(false);

  const startDraw = () => {
    setBbox(null);
    setPoints([]);
    window.dispatchEvent(new Event("aotw:start-bbox"));
  };

  const clearAll = () => {
    setBbox(null);
    setPoints([]);
  };

  const runHeatmap = async () => {
    if (!bbox) {
      toast.error("Draw a bounding box first");
      return;
    }
    setLoading(true);
    try {
      const r = await ext.heatmap({
        bbox,
        grid_step_km: step,
        user_type: userType,
      });
      const pts = (r?.points || r?.grid || r || []).map((p) => {
        const grade = p.grade || gradeFromScore(p.score);
        return {
          lat: p.lat,
          lon: p.lon,
          color: gradeColor(grade),
          label: `<div class="mono text-[11px]"><div>${p.location_name || ""}</div><div style="color:${gradeColor(grade)}">${grade} · ${fmt(p.score, 1)}</div><div style="color:#5C667A">${fmtCoord(p.lat)}, ${fmtCoord(p.lon)}</div></div>`,
        };
      });
      setPoints(pts);
    } catch (e) {
      toast.error(`Heatmap failed: ${e?.message || "unknown"}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative h-[calc(100vh-49px)]" data-testid="heatmap-page">
      <LeafletMap
        center={[60.0, 15.0]}
        zoom={4}
        bbox={bbox}
        onBbox={setBbox}
        heatmapPoints={points}
      />

      {/* Top right controls */}
      <div className="absolute top-3 right-3 z-[400] panel p-3 w-[260px] space-y-3">
        <div className="label-overline">HEATMAP CONTROLS</div>

        <div>
          <div className="label-overline mb-1">USER TYPE</div>
          <select
            data-testid="heatmap-user-type"
            value={userType}
            onChange={(e) => setUserType(e.target.value)}
            className="mono w-full bg-[#0A0E1A] border border-[#1E2535] focus:border-[#00C2FF] outline-none px-2 py-1.5 text-[12px] text-white"
            style={{ borderRadius: 0 }}
          >
            {USER_TYPES.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </div>

        <div>
          <div className="label-overline mb-1">GRID STEP (km)</div>
          <div className="grid grid-cols-3 gap-1">
            {STEPS.map((s) => (
              <button
                key={s}
                onClick={() => setStep(s)}
                data-testid={`heatmap-step-${s}`}
                className={`mono text-[11px] py-1.5 ${step === s ? "" : "text-[#8B95A5]"}`}
                style={{
                  background: step === s ? "#00C2FF" : "transparent",
                  color: step === s ? "#0A0E1A" : "#8B95A5",
                  border: `1px solid ${step === s ? "#00C2FF" : "#1E2535"}`,
                  borderRadius: 0,
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <button
            data-testid="heatmap-draw-bbox"
            onClick={startDraw}
            className="mono inline-flex items-center justify-center gap-1.5 px-2 py-2 text-[11px] border border-[#1E2535] hover:border-[#00C2FF] hover:text-[#00C2FF] text-[#8B95A5]"
            style={{ borderRadius: 0 }}
          >
            <Square size={12} /> DRAW BBOX
          </button>
          <button
            data-testid="heatmap-clear"
            onClick={clearAll}
            className="mono inline-flex items-center justify-center gap-1.5 px-2 py-2 text-[11px] border border-[#1E2535] hover:border-[#FF3B30] hover:text-[#FF3B30] text-[#8B95A5]"
            style={{ borderRadius: 0 }}
          >
            <X size={12} /> CLEAR
          </button>
        </div>

        <button
          data-testid="heatmap-run"
          onClick={runHeatmap}
          disabled={loading || !bbox}
          className="mono w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 text-[12px] font-medium"
          style={{
            background: !bbox ? "#1E2535" : "#00C2FF",
            color: !bbox ? "#5C667A" : "#0A0E1A",
            borderRadius: 0,
          }}
        >
          <Play size={12} /> {loading ? "RUNNING…" : "RUN HEATMAP"}
        </button>

        {bbox && (
          <div className="mono text-[10px] text-[#5C667A] leading-tight">
            <div>N {bbox.n.toFixed(3)} · S {bbox.s.toFixed(3)}</div>
            <div>E {bbox.e.toFixed(3)} · W {bbox.w.toFixed(3)}</div>
            <div className="mt-1 text-[#8B95A5]">
              {points.length} points
            </div>
          </div>
        )}

        {/* Legend */}
        <div className="border-t border-[#1E2535] pt-2">
          <div className="label-overline mb-1.5">LEGEND</div>
          <div className="grid grid-cols-2 gap-1 mono text-[10px]">
            {[
              ["A+", "#30D158"],
              ["A", "#00C2FF"],
              ["B", "#00D4B2"],
              ["C", "#FF9F0A"],
              ["D", "#FF6B00"],
              ["F", "#FF3B30"],
            ].map(([g, c]) => (
              <div key={g} className="flex items-center gap-1.5">
                <span
                  className="w-2.5 h-2.5 inline-block rounded-full"
                  style={{ background: c, boxShadow: `0 0 6px ${c}` }}
                />
                <span className="text-white">{g}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Top-left readout */}
      <div className="absolute top-3 left-3 z-[400] panel px-3 py-2">
        <div className="label-overline">HEATMAP MODE</div>
        <div className="mono text-[11px] text-white mt-0.5">
          drag on map to define area · {step}km grid
        </div>
      </div>
    </div>
  );
}
