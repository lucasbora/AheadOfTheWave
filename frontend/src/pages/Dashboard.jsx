import React, { useEffect, useMemo, useState } from "react";
import LeafletMap from "../components/LeafletMap";
import InvestmentGradeCard from "../components/InvestmentGradeCard";
import RiskBreakdownPanel from "../components/RiskBreakdownPanel";
import ClaudeAuditPanel from "../components/ClaudeAuditPanel";
import DataLineageDrawer from "../components/DataLineageDrawer";
import { ext, internal, loadSettings } from "../lib/api";
import { fmtCoord } from "../lib/grade";
import { Bookmark, Crosshair, Database, FileJson } from "lucide-react";
import { toast } from "sonner";

const USER_TYPES = [
  "data_center",
  "industrial_park",
  "logistics",
  "residential_developer",
  "generic_investor",
];

const DEFAULT_LATLON = { lat: 60.1699, lon: 24.9384 }; // Helsinki

export default function Dashboard() {
  const [settings, setSettings] = useState(loadSettings());
  const [name, setName] = useState("Helsinki HQ");
  const [userType, setUserType] = useState(settings.defaultUserType);
  const [coord, setCoord] = useState(DEFAULT_LATLON);
  const [score, setScore] = useState(null);
  const [audit, setAudit] = useState(null);
  const [lineage, setLineage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [savedLocations, setSavedLocations] = useState([]);
  const [showAudit, setShowAudit] = useState(false);

  useEffect(() => {
    const fn = () => setSettings(loadSettings());
    window.addEventListener("aotw:settings-changed", fn);
    return () => window.removeEventListener("aotw:settings-changed", fn);
  }, []);

  useEffect(() => {
    internal.listLocations().then(setSavedLocations).catch(() => {});
  }, []);

  const handleScore = async () => {
    setLoading(true);
    setScore(null);
    setAudit(null);
    setLineage(null);
    setShowAudit(true);
    const body = {
      lat: coord.lat,
      lon: coord.lon,
      user_type: userType,
      location_name: name,
    };
    try {
      const [s, a, ln] = await Promise.allSettled([
        ext.scoreInvestment(body),
        ext.explainInvestment({
          lat: coord.lat,
          lon: coord.lon,
          user_type: userType,
        }),
        ext.lineage({ lat: coord.lat, lon: coord.lon, user_type: userType }),
      ]);
      if (s.status === "fulfilled") setScore(s.value);
      else
        toast.error(
          `Score endpoint failed: ${s.reason?.message || "request error"}`
        );
      if (a.status === "fulfilled") setAudit(a.value);
      if (ln.status === "fulfilled") setLineage(ln.value);
    } catch (e) {
      toast.error(`Backend unreachable at ${loadSettings().apiBaseUrl}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!score) {
      toast.error("Score the location first");
      return;
    }
    try {
      const saved = await internal.saveLocation({
        name,
        lat: coord.lat,
        lon: coord.lon,
        user_type: userType,
        grade: score.grade,
        score: score.score,
        label: score.label || score.grade_label,
        payload: score,
      });
      setSavedLocations((cur) => [saved, ...cur]);
      toast.success(`Saved ${name}`);
    } catch (e) {
      toast.error("Save failed");
    }
  };

  const handleAddToCompare = async () => {
    if (!score) {
      toast.error("Score the location first");
      return;
    }
    try {
      await internal.addLeaderboard({
        name,
        lat: coord.lat,
        lon: coord.lon,
        user_type: userType,
        grade: score.grade,
        score: score.score,
        label: score.label || score.grade_label,
      });
      toast.success(`Added ${name} to leaderboard`);
    } catch (e) {
      toast.error("Add failed");
    }
  };

  const marker = useMemo(
    () => ({ lat: coord.lat, lon: coord.lon, grade: score?.grade }),
    [coord.lat, coord.lon, score?.grade]
  );

  return (
    <div className="grid grid-cols-[300px_1fr_380px] h-[calc(100vh-49px)]">
      {/* LEFT SIDEBAR */}
      <aside
        className="border-r border-[#1E2535] bg-[#0B101D] overflow-auto"
        data-testid="dashboard-left-sidebar"
      >
        <div className="px-4 py-3 border-b border-[#1E2535]">
          <div className="label-overline">LOCATION INPUT</div>
        </div>

        <div className="p-4 space-y-4">
          <div>
            <div className="label-overline mb-1.5">Site name</div>
            <input
              data-testid="input-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mono w-full bg-transparent border border-[#1E2535] focus:border-[#00C2FF] outline-none px-3 py-2 text-sm text-white placeholder:text-[#5C667A]"
              style={{ borderRadius: 0 }}
              placeholder="Helsinki HQ"
            />
          </div>

          <div>
            <div className="label-overline mb-1.5">User Type</div>
            <select
              data-testid="select-user-type"
              value={userType}
              onChange={(e) => setUserType(e.target.value)}
              className="mono w-full bg-[#0A0E1A] border border-[#1E2535] focus:border-[#00C2FF] outline-none px-3 py-2 text-sm text-white"
              style={{ borderRadius: 0 }}
            >
              {USER_TYPES.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <div className="label-overline mb-1.5">Latitude</div>
              <input
                data-testid="input-lat"
                type="number"
                step="0.0001"
                value={coord.lat}
                onChange={(e) =>
                  setCoord((c) => ({ ...c, lat: parseFloat(e.target.value) }))
                }
                className="mono w-full bg-transparent border border-[#1E2535] focus:border-[#00C2FF] outline-none px-3 py-2 text-sm text-white"
                style={{ borderRadius: 0 }}
              />
            </div>
            <div>
              <div className="label-overline mb-1.5">Longitude</div>
              <input
                data-testid="input-lon"
                type="number"
                step="0.0001"
                value={coord.lon}
                onChange={(e) =>
                  setCoord((c) => ({ ...c, lon: parseFloat(e.target.value) }))
                }
                className="mono w-full bg-transparent border border-[#1E2535] focus:border-[#00C2FF] outline-none px-3 py-2 text-sm text-white"
                style={{ borderRadius: 0 }}
              />
            </div>
          </div>

          <div className="mono text-[10px] text-[#5C667A] flex items-center gap-1">
            <Crosshair size={10} /> click map to drop pin
          </div>

          <button
            data-testid="score-location-button"
            disabled={loading}
            onClick={handleScore}
            className="mono w-full px-4 py-2.5 text-[12px] font-medium tracking-wider"
            style={{
              background: loading ? "#1E2535" : "#00C2FF",
              color: loading ? "#5C667A" : "#0A0E1A",
              borderRadius: 0,
            }}
          >
            {loading ? "▸ SCORING…" : "SCORE THIS LOCATION"}
          </button>

          <div className="grid grid-cols-2 gap-2">
            <button
              data-testid="save-location-button"
              onClick={handleSave}
              className="mono inline-flex items-center justify-center gap-1.5 px-3 py-2 text-[11px] border border-[#1E2535] hover:border-[#00C2FF] hover:text-[#00C2FF] text-[#8B95A5]"
              style={{ borderRadius: 0 }}
            >
              <Bookmark size={12} /> SAVE
            </button>
            <button
              data-testid="add-compare-button"
              onClick={handleAddToCompare}
              className="mono inline-flex items-center justify-center gap-1.5 px-3 py-2 text-[11px] border border-[#1E2535] hover:border-[#00C2FF] hover:text-[#00C2FF] text-[#8B95A5]"
              style={{ borderRadius: 0 }}
            >
              + COMPARE
            </button>
          </div>

          <button
            data-testid="open-lineage-button"
            onClick={() => setDrawerOpen(true)}
            className="mono w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 text-[11px] border border-[#1E2535] hover:border-[#00C2FF] hover:text-[#00C2FF] text-[#8B95A5]"
            style={{ borderRadius: 0 }}
          >
            <Database size={12} /> DATA LINEAGE
          </button>
        </div>

        <div className="border-t border-[#1E2535] px-4 py-3">
          <div className="label-overline mb-2">SAVED ({savedLocations.length})</div>
          <div className="space-y-1.5 max-h-[280px] overflow-auto">
            {savedLocations.length === 0 && (
              <div className="mono text-[11px] text-[#5C667A]">
                no saved locations
              </div>
            )}
            {savedLocations.map((l) => (
              <button
                key={l.id}
                onClick={() => {
                  setName(l.name);
                  setUserType(l.user_type);
                  setCoord({ lat: l.lat, lon: l.lon });
                }}
                className="w-full text-left p-2 border border-[#1E2535] hover:bg-[#131A2B]"
                data-testid={`saved-${l.id}`}
                style={{ borderRadius: 0 }}
              >
                <div className="flex items-center justify-between">
                  <span className="text-[12px] text-white truncate">
                    {l.name}
                  </span>
                  {l.grade && (
                    <span
                      className="mono text-[10px] px-1.5 py-0.5"
                      style={{
                        color: "#00C2FF",
                        background: "rgba(0,194,255,0.10)",
                        border: "1px solid rgba(0,194,255,0.4)",
                      }}
                    >
                      {l.grade}
                    </span>
                  )}
                </div>
                <div className="mono text-[10px] text-[#5C667A] mt-0.5">
                  {fmtCoord(l.lat)}, {fmtCoord(l.lon)}
                </div>
              </button>
            ))}
          </div>
        </div>
      </aside>

      {/* MAP CENTER */}
      <main className="relative" data-testid="dashboard-map-area">
        <LeafletMap
          center={[coord.lat, coord.lon]}
          zoom={6}
          marker={marker}
          onClick={(lat, lon) => setCoord({ lat, lon })}
        />
        <div
          className="absolute top-3 left-16 z-[400] panel px-3 py-2"
          data-testid="coord-readout"
        >
          <div className="label-overline">CURRENT PIN</div>
          <div className="mono text-[12px] mt-0.5">
            <span className="text-white">{fmtCoord(coord.lat)}</span>
            <span className="text-[#5C667A]"> · </span>
            <span className="text-white">{fmtCoord(coord.lon)}</span>
          </div>
        </div>
        <div className="absolute bottom-3 right-3 z-[400] panel px-2 py-1 mono text-[10px] text-[#5C667A] flex items-center gap-2">
          <FileJson size={10} /> CartoDB Dark Matter · OSM
        </div>
      </main>

      {/* RIGHT PANEL */}
      <aside
        className="border-l border-[#1E2535] bg-[#0B101D] overflow-auto"
        data-testid="dashboard-right-panel"
      >
        <div className="p-3 space-y-3">
          <InvestmentGradeCard data={score} loading={loading} />
          {(showAudit || score) && (
            <>
              <RiskBreakdownPanel data={score} />
              <ClaudeAuditPanel data={audit} loading={loading} />
            </>
          )}
        </div>
      </aside>

      <DataLineageDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        lineage={lineage}
        context={{ name, ...coord, user_type: userType }}
      />
    </div>
  );
}
