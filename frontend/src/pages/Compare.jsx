import React, { useEffect, useState } from "react";
import { internal, ext, loadSettings } from "../lib/api";
import GradeBadge from "../components/GradeBadge";
import ScoreBar from "../components/ScoreBar";
import { fmt, fmtCoord, gradeColor } from "../lib/grade";
import { Plus, Trash2, RefreshCw } from "lucide-react";
import { toast } from "sonner";

const USER_TYPES = [
  "data_center",
  "industrial_park",
  "logistics",
  "residential_developer",
  "generic_investor",
];

export default function Compare() {
  const [rows, setRows] = useState([]);
  const [userType, setUserType] = useState(loadSettings().defaultUserType);
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({ name: "", lat: "", lon: "" });
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const r = await internal.listLeaderboard();
      setRows(
        [...r].sort(
          (a, b) => (Number(b.score) || -Infinity) - (Number(a.score) || -Infinity)
        )
      );
    } catch (e) {
      toast.error("Failed to load leaderboard");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const top = rows[0];

  const handleAdd = async () => {
    if (!draft.name || draft.lat === "" || draft.lon === "") {
      toast.error("Name, lat, lon required");
      return;
    }
    setBusy(true);
    try {
      const body = {
        lat: parseFloat(draft.lat),
        lon: parseFloat(draft.lon),
        user_type: userType,
        location_name: draft.name,
      };
      const s = await ext.scoreInvestment(body);
      await internal.addLeaderboard({
        name: draft.name,
        lat: parseFloat(draft.lat),
        lon: parseFloat(draft.lon),
        user_type: userType,
        grade: s.grade,
        score: s.score,
        label: s.label || s.grade_label,
      });
      setDraft({ name: "", lat: "", lon: "" });
      setAdding(false);
      await load();
      toast.success(`Added ${draft.name}`);
    } catch (e) {
      toast.error(`Score failed: ${e?.message || "unknown"}`);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (id) => {
    await internal.deleteLeaderboardEntry(id);
    await load();
  };

  const handleRescoreAll = async () => {
    setBusy(true);
    try {
      // Re-score each row with current user type
      for (const r of rows) {
        try {
          const s = await ext.scoreInvestment({
            lat: r.lat,
            lon: r.lon,
            user_type: userType,
            location_name: r.name,
          });
          await internal.deleteLeaderboardEntry(r.id);
          await internal.addLeaderboard({
            name: r.name,
            lat: r.lat,
            lon: r.lon,
            user_type: userType,
            grade: s.grade,
            score: s.score,
            label: s.label || s.grade_label,
          });
        } catch (e) {
          /* keep going */
        }
      }
      await load();
      toast.success("Rescored all");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="p-5" data-testid="compare-page">
      <div className="flex items-end justify-between mb-4 flex-wrap gap-3">
        <div>
          <div className="label-overline">RANKING · LEADERBOARD</div>
          <h1 className="text-2xl tracking-tight font-medium mt-1">
            Compare Locations
          </h1>
          <div className="mono text-[11px] text-[#5C667A] mt-1">
            Up to 10 sites ranked by composite score · scored against current user type
          </div>
        </div>

        <div className="flex items-center gap-2">
          <select
            data-testid="compare-user-type"
            value={userType}
            onChange={(e) => setUserType(e.target.value)}
            className="mono bg-[#0A0E1A] border border-[#1E2535] focus:border-[#00C2FF] outline-none px-3 py-2 text-[12px] text-white"
            style={{ borderRadius: 0 }}
          >
            {USER_TYPES.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
          <button
            data-testid="compare-rescore"
            onClick={handleRescoreAll}
            disabled={busy || rows.length === 0}
            className="mono inline-flex items-center gap-1.5 px-3 py-2 text-[11px] border border-[#1E2535] hover:border-[#00C2FF] hover:text-[#00C2FF] text-[#8B95A5]"
            style={{ borderRadius: 0 }}
          >
            <RefreshCw size={12} /> RESCORE ALL
          </button>
          <button
            data-testid="compare-add-button"
            onClick={() => setAdding((v) => !v)}
            className="mono inline-flex items-center gap-1.5 px-4 py-2 text-[12px] font-medium"
            style={{
              background: "#00C2FF",
              color: "#0A0E1A",
              borderRadius: 0,
            }}
          >
            <Plus size={14} /> ADD LOCATION
          </button>
        </div>
      </div>

      {adding && (
        <div className="panel mb-3 p-3 grid grid-cols-[1fr_120px_120px_auto] gap-2 items-end">
          <div>
            <div className="label-overline mb-1">Name</div>
            <input
              data-testid="compare-input-name"
              value={draft.name}
              onChange={(e) =>
                setDraft((d) => ({ ...d, name: e.target.value }))
              }
              className="mono w-full bg-transparent border border-[#1E2535] focus:border-[#00C2FF] outline-none px-2 py-1.5 text-sm"
              style={{ borderRadius: 0 }}
            />
          </div>
          <div>
            <div className="label-overline mb-1">Lat</div>
            <input
              data-testid="compare-input-lat"
              value={draft.lat}
              onChange={(e) =>
                setDraft((d) => ({ ...d, lat: e.target.value }))
              }
              className="mono w-full bg-transparent border border-[#1E2535] focus:border-[#00C2FF] outline-none px-2 py-1.5 text-sm"
              style={{ borderRadius: 0 }}
            />
          </div>
          <div>
            <div className="label-overline mb-1">Lon</div>
            <input
              data-testid="compare-input-lon"
              value={draft.lon}
              onChange={(e) =>
                setDraft((d) => ({ ...d, lon: e.target.value }))
              }
              className="mono w-full bg-transparent border border-[#1E2535] focus:border-[#00C2FF] outline-none px-2 py-1.5 text-sm"
              style={{ borderRadius: 0 }}
            />
          </div>
          <button
            data-testid="compare-confirm-add"
            onClick={handleAdd}
            disabled={busy}
            className="mono px-4 py-2 text-[11px] font-medium"
            style={{
              background: "#00C2FF",
              color: "#0A0E1A",
              borderRadius: 0,
            }}
          >
            {busy ? "…" : "SCORE & ADD"}
          </button>
        </div>
      )}

      {/* Table */}
      <div className="panel">
        <div className="grid grid-cols-[40px_1fr_1.4fr_60px_80px_36px] items-center px-4 py-2 border-b border-[#1E2535] label-overline">
          <span>RANK</span>
          <span>LOCATION</span>
          <span>SCORE</span>
          <span>GRADE</span>
          <span className="text-right">Δ TOP</span>
          <span></span>
        </div>
        <div className="divide-y divide-[#1E2535]">
          {rows.length === 0 && (
            <div className="px-4 py-8 mono text-[11px] text-[#5C667A] text-center">
              No locations yet — add some to compare.
            </div>
          )}
          {rows.slice(0, 10).map((r, i) => {
            const isTop = i === 0;
            const isLast = i === rows.length - 1 && rows.length > 1;
            const delta =
              top?.score != null && r.score != null
                ? Number(r.score) - Number(top.score)
                : null;
            const rowBg = isTop
              ? "rgba(0,194,255,0.08)"
              : isLast
                ? "rgba(255,59,48,0.06)"
                : "transparent";
            const rankColor = isTop
              ? "#00C2FF"
              : isLast
                ? "#FF3B30"
                : "#8B95A5";
            return (
              <div
                key={r.id}
                className="grid grid-cols-[40px_1fr_1.4fr_60px_80px_36px] items-center px-4 py-2.5"
                style={{ background: rowBg }}
                data-testid={`compare-row-${i + 1}`}
              >
                <span
                  className="mono text-[14px] font-medium"
                  style={{ color: rankColor }}
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div>
                  <div className="text-[13px] text-white truncate">
                    {r.name}
                  </div>
                  <div className="mono text-[10px] text-[#5C667A]">
                    {fmtCoord(r.lat)}, {fmtCoord(r.lon)} · {r.user_type}
                  </div>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1">
                      <ScoreBar
                        value={r.score || 0}
                        grade={r.grade}
                        height={6}
                      />
                    </div>
                    <span
                      className="mono text-[12px] tabular-nums"
                      style={{ color: gradeColor(r.grade) }}
                    >
                      {fmt(r.score, 2)}
                    </span>
                  </div>
                </div>
                <GradeBadge
                  grade={r.grade}
                  testId={`compare-grade-${i + 1}`}
                />
                <span
                  className="mono text-[11px] text-right tabular-nums"
                  style={{
                    color:
                      delta == null
                        ? "#5C667A"
                        : delta === 0
                          ? "#00C2FF"
                          : delta < 0
                            ? "#FF3B30"
                            : "#30D158",
                  }}
                >
                  {delta == null
                    ? "—"
                    : `${delta >= 0 ? "+" : ""}${delta.toFixed(2)}`}
                </span>
                <button
                  onClick={() => handleDelete(r.id)}
                  className="text-[#5C667A] hover:text-[#FF3B30] flex justify-end"
                  data-testid={`compare-delete-${i + 1}`}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
