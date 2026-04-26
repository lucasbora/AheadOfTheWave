import React, { useEffect, useState } from "react";
import { ext, loadSettings } from "../lib/api";
import ScoreBar from "../components/ScoreBar";
import AlertChip from "../components/AlertChip";
import VesilakiModal from "../components/VesilakiModal";
import { Check, FlaskConical, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  ResponsiveContainer, Tooltip, ReferenceLine,
} from "recharts";

const LUMI = { lat: 64.22, lon: 27.72, name: "LUMI Supercomputer · Kajaani" };

const GRADE_COLORS = {
  "A+": "#30D158", A: "#00C2FF", B: "#00D4B2",
  C: "#FF9F0A", D: "#FF6B00", F: "#FF3B30",
};

function gradeColor(g) { return GRADE_COLORS[g] || "#8B95A5"; }

function ScoreBox({ label, score, grade, highlight }) {
  const color = gradeColor(grade);
  return (
    <div className="panel" style={highlight ? { borderColor: "#30D158" } : {}}>
      <div className="px-4 py-2.5 border-b border-[#1E2535]">
        <div className="label-overline">{label}</div>
      </div>
      <div className="p-4">
        {score != null ? (
          <>
            <div className="flex items-end justify-between mb-2">
              <span className="mono text-[36px] font-medium" style={{ color }}>
                {grade}
              </span>
              <span className="mono text-[28px]" style={{ color }}>
                {Number(score).toFixed(1)}
              </span>
            </div>
            <ScoreBar value={score} grade={grade} />
          </>
        ) : (
          <div className="mono text-[13px] text-[#5C667A] mt-2">no data</div>
        )}
      </div>
    </div>
  );
}

function ComponentBar({ label, value, max, color }) {
  return (
    <div className="mb-2">
      <div className="flex justify-between mono text-[11px] mb-1">
        <span className="text-[#8B95A5]">{label}</span>
        <span style={{ color }}>{Number(value).toFixed(1)} / {max}</span>
      </div>
      <div className="gauge-track">
        <div className="gauge-fill" style={{
          width: `${(value / max) * 100}%`,
          background: color,
          height: "4px",
        }} />
      </div>
    </div>
  );
}

export default function FinlandOracle() {
  const [backtest, setBacktest] = useState(null);
  const [loading, setLoading] = useState(false);
  const [legalOpen, setLegalOpen] = useState(false);
  const year = 2018;

  const loadBacktest = async (yr) => {
    setLoading(true);
    try {
      const base = (loadSettings().apiBaseUrl || "http://127.0.0.1:8000").replace(/\/+$/, "");
      const r = await fetch(`${base}/api/v1/finland/kajaani-backtest?year=${yr}`);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      setBacktest(await r.json());
    } catch (e) {
      toast.error(`Backtest failed: ${e?.message || "unknown"}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBacktest(year);
    // baseline is intentionally fixed for demo storytelling: "before 2018"
  }, [year]);

  const score_year    = backtest?.score_year || {};
  const score_current = backtest?.score_current || {};
  const components    = score_year?.components || {};
  const raw           = score_year?.raw_inputs || {};
  const sources       = score_year?.data_sources || {};
  const availability  = score_year?.data_availability || {};
  const timeline      = backtest?.timeline || [];
  const advisor       = backtest?.advisor;
  const verified      = backtest?.verified;
  const syke          = score_year?.syke || {};

  // Galileo data from old oracle endpoint if still available
  const [galileo, setGalileo] = useState(null);
  useEffect(() => {
    ext.finlandOracle({ lat: LUMI.lat, lon: LUMI.lon, location_name: LUMI.name })
      .then(r => setGalileo(r)).catch(() => {});
  }, []);

  const subsidence  = galileo?.galileo?.series || [];
  const alertLevel  = galileo?.galileo?.alert_level || "green";
  const watershed   = galileo?.watershed || {};

  return (
    <div className="p-5 space-y-4" data-testid="finland-oracle-page">

      {/* Header */}
      <div className="panel p-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="label-overline">CASSINI HACKATHON · VALIDATION ENGINE</div>
            <h1 className="text-2xl tracking-tight font-medium mt-1">
              Kajaani Investment Oracle
            </h1>
            <div className="mono text-[11px] text-[#5C667A] mt-1">
              Real data: Sentinel-1 SAR (GEE) · Sentinel-2 NDWI · Visual Crossing weather · SYKE
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => loadBacktest(year)}
              className="mono px-3 py-2 text-[11px]"
              style={{
                background: "#00C2FF",
                color: "#0A0E1A",
                border: "1px solid #00C2FF",
                borderRadius: 0,
              }}
              data-testid="year-btn-before-2018"
            >
              BEFORE 2018
            </button>
            <button onClick={() => loadBacktest(year)} disabled={loading}
              className="mono inline-flex items-center gap-1.5 px-3 py-2 text-[11px] border border-[#1E2535] hover:border-[#00C2FF] hover:text-[#00C2FF] text-[#8B95A5]"
              style={{ borderRadius: 0 }}>
              <RefreshCw size={12} /> {loading ? "LOADING…" : "REFRESH"}
            </button>
            <button onClick={() => setLegalOpen(true)}
              className="mono inline-flex items-center gap-1.5 px-3 py-2 text-[12px] font-medium"
              style={{ background: "#FF9F0A", color: "#0A0E1A", borderRadius: 0 }}>
              <FlaskConical size={12} /> VESILAKI CHECK
            </button>
          </div>
        </div>
      </div>

      {/* Site + Score columns */}
      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_1fr] gap-3">

        {/* Site card */}
        <div className="panel">
          <div className="px-4 py-2.5 border-b border-[#1E2535]">
            <div className="label-overline">SITE</div>
            <div className="text-[14px] mt-0.5">LUMI Supercomputer</div>
          </div>
          <div className="p-4 space-y-2">
            {[
              ["lat", "+64.2200°N"], ["lon", "+27.7200°E"],
              ["city", "Kajaani · Finland"],
              ["built", "EuroHPC LUMI · 2021"],
              ["compute", "~376 PFLOPS"],
            ].map(([k, v]) => (
              <div key={k} className="mono text-[11px]">
                <span className="text-[#5C667A]">{k} </span>
                <span className="text-white">{v}</span>
              </div>
            ))}
            {verified && (
              <div className="mt-3 pt-3 border-t border-[#1E2535]">
                <span className="mono text-[10px] inline-flex items-center gap-1 px-2 py-1"
                  style={{ color: "#30D158", background: "rgba(48,209,88,0.10)", border: "1px solid rgba(48,209,88,0.4)" }}
                  data-testid="finland-verified">
                  <Check size={10} /> MODEL VALIDATED
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Score for selected year */}
        <div className="panel">
          <div className="px-4 py-2.5 border-b border-[#1E2535] flex justify-between items-center">
            <div>
              <div className="label-overline">SCORE · BEFORE 2018</div>
              <div className="text-[13px] mt-0.5">What a pre-2018 investor would see</div>
            </div>
            {verified && <span className="mono text-[10px] px-2 py-1"
              style={{ color: "#30D158", background: "rgba(48,209,88,0.10)", border: "1px solid rgba(48,209,88,0.4)" }}>
              <Check size={10} className="inline mr-1" />VERIFIED
            </span>}
          </div>
          <div className="p-4">
            {score_year.score != null ? (
              <>
                <div className="flex items-end justify-between mb-3">
                  <span className="mono text-[40px]" style={{ color: gradeColor(score_year.grade) }}>
                    {score_year.grade}
                  </span>
                  <span className="mono text-[32px] text-white">
                    {Number(score_year.score).toFixed(1)}<span className="text-[#5C667A] text-[16px]">/100</span>
                  </span>
                </div>
                <ScoreBar value={score_year.score} grade={score_year.grade} />
                <div className="mono text-[11px] text-[#8B95A5] mt-2">{score_year.grade_label}</div>

                {/* Component breakdown */}
                <div className="mt-4 space-y-1">
                  <ComponentBar label={`S1 SAR flood freq: ${raw.flood_freq}`} value={components.s1_flood_contribution} max={30} color="#00C2FF" />
                  <ComponentBar label={`CDD ${raw.cdd} (free cooling)`} value={components.cooling_cdd_contribution} max={25} color="#30D158" />
                  <ComponentBar label={`Drought index: ${raw.drought_index}`} value={components.drought_contribution} max={20} color="#00D4B2" />
                  <ComponentBar label={`GW class: ${raw.groundwater_class}`} value={components.groundwater_contribution} max={15} color="#FF9F0A" />
                  <ComponentBar label={`S2 NDWI: ${raw.ndwi}`} value={components.surface_water_contribution} max={10} color="#8B95A5" />
                </div>
              </>
            ) : (
              <div className="mono text-[12px] text-[#5C667A]">loading…</div>
            )}
          </div>
        </div>

        {/* Current score */}
        <div className="panel">
          <div className="px-4 py-2.5 border-b border-[#1E2535]">
            <div className="label-overline">SCORE · CURRENT (2026)</div>
            <div className="text-[13px] mt-0.5">Today's conditions</div>
          </div>
          <div className="p-4">
            {score_current.score != null ? (
              <>
                <div className="flex items-end justify-between mb-3">
                  <span className="mono text-[40px]" style={{ color: gradeColor(score_current.grade) }}>
                    {score_current.grade}
                  </span>
                  <span className="mono text-[32px] text-white">
                    {Number(score_current.score).toFixed(1)}<span className="text-[#5C667A] text-[16px]">/100</span>
                  </span>
                </div>
                <ScoreBar value={score_current.score} grade={score_current.grade} />
                <div className="mono text-[11px] text-[#8B95A5] mt-2">{score_current.grade_label}</div>
                <div className="mt-3 pt-3 border-t border-[#1E2535] mono text-[11px]">
                  <span className="text-[#5C667A]">delta from before 2018: </span>
                  <span style={{ color: backtest?.delta >= 0 ? "#30D158" : "#FF3B30" }}>
                    {backtest?.delta >= 0 ? "+" : ""}{backtest?.delta?.toFixed(2)}
                  </span>
                </div>
              </>
            ) : (
              <div className="mono text-[12px] text-[#5C667A]">loading…</div>
            )}
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div className="panel">
        <div className="px-4 py-2.5 border-b border-[#1E2535]">
          <div className="label-overline">VALIDATION TIMELINE</div>
          <div className="text-[13px] mt-0.5">Model prediction vs real-world outcome</div>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-[#1E2535]">
          {timeline.map((t) => (
            <div key={t.year} className="p-4">
              <div className="mono text-[20px] text-white">{t.year}</div>
              <div className="text-[11px] text-[#8B95A5] mt-1 mb-2">{t.event}</div>
              {t.score != null ? (
                <span className="mono text-[16px]" style={{ color: gradeColor(t.grade) }}>
                  {t.grade} · {Number(t.score).toFixed(1)}
                </span>
              ) : t.year === 2021 ? (
                <span className="mono text-[11px] px-2 py-0.5"
                  style={{ color: "#30D158", background: "rgba(48,209,88,0.10)", border: "1px solid rgba(48,209,88,0.3)" }}>
                  BUILT ✓
                </span>
              ) : (
                <span className="mono text-[11px] text-[#5C667A]">—</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Claude advisor */}
      {advisor && (
        <div className="panel">
          <div className="px-4 py-2.5 border-b border-[#1E2535]">
            <div className="label-overline">CLAUDE · INVESTMENT ADVISOR</div>
            <div className="text-[13px] mt-0.5">Water-focused analysis · Claude Sonnet 4.6</div>
          </div>
          <div className="p-5">
            <pre className="mono text-[12.5px] text-white whitespace-pre-wrap leading-relaxed">
              {advisor}
            </pre>
          </div>
        </div>
      )}

      {/* Data sources */}
      <div className="panel">
        <div className="px-4 py-2.5 border-b border-[#1E2535]">
          <div className="label-overline">DATA SOURCES</div>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-[#1E2535]">
          {[
            ["Sentinel-1", "S1 SAR GEE", availability.s1_gee, sources.sentinel_1],
            ["Sentinel-2", "CDSE NDWI", availability.s2_geotiff, sources.sentinel_2],
            ["Weather", "Visual Crossing", availability.weather_csv, sources.weather],
            ["SYKE", "Gov. data", availability.syke, sources.syke],
          ].map(([name, short, avail, src]) => (
            <div key={name} className="p-3">
              <div className="label-overline">{name}</div>
              <div className="mono text-[11px] mt-1" style={{ color: avail ? "#30D158" : "#FF9F0A" }}>
                {avail ? "LIVE" : "FALLBACK"}
              </div>
              <div className="mono text-[9px] text-[#5C667A] mt-1 truncate" title={src}>{short}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Galileo subsidence (from old oracle if available) */}
      {subsidence.length > 0 && (
        <div className="panel">
          <div className="px-4 py-2.5 border-b border-[#1E2535] flex items-center justify-between">
            <div>
              <div className="label-overline">GALILEO · GROUND DEFORMATION</div>
              <div className="text-[13px] mt-0.5">NKG2016LU GIA model — simulated</div>
            </div>
            <AlertChip level={alertLevel} testId="finland-galileo-alert" />
          </div>
          <div className="p-3" style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={subsidence}>
                <CartesianGrid stroke="#1E2535" strokeDasharray="2 2" />
                <XAxis dataKey="month" stroke="#5C667A" fontSize={10} tickLine={false} axisLine={{ stroke: "#1E2535" }} />
                <YAxis stroke="#5C667A" fontSize={10} tickLine={false} axisLine={{ stroke: "#1E2535" }} width={35} />
                <Tooltip contentStyle={{ background: "#0B101D", border: "1px solid #1E2535", borderRadius: 0, fontSize: 11 }} />
                <ReferenceLine y={0} stroke="#1E2535" />
                <Line type="monotone" dataKey="gia_uplift" stroke="#30D158" strokeWidth={1.5} dot={false} name="GIA Uplift (mm)" />
                <Line type="monotone" dataKey="net_displacement" stroke="#00C2FF" strokeWidth={1.5} dot={false} name="Net Disp. (mm)" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      <VesilakiModal open={legalOpen} onClose={() => setLegalOpen(false)}
        syke={{ flood_zone: "None", groundwater_class: raw.groundwater_class, abstraction_m3_day: 1500, lat: LUMI.lat, lon: LUMI.lon }} />
    </div>
  );
}
