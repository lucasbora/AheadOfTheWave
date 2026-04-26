import React, { useEffect, useState } from "react";
import { X } from "lucide-react";
import { loadSettings, saveSettings } from "../lib/api";

const USER_TYPES = [
  "data_center",
  "industrial_park",
  "logistics",
  "residential_developer",
  "generic_investor",
];

export const SettingsDialog = ({ open, onOpenChange }) => {
  const [api, setApi] = useState("");
  const [ut, setUt] = useState("data_center");

  useEffect(() => {
    if (open) {
      const s = loadSettings();
      setApi(s.apiBaseUrl);
      setUt(s.defaultUserType);
    }
  }, [open]);

  if (!open) return null;

  const handleSave = () => {
    saveSettings({ apiBaseUrl: api.trim(), defaultUserType: ut });
    onOpenChange(false);
    window.dispatchEvent(new Event("aotw:settings-changed"));
  };

  return (
    <div
      className="fixed inset-0 z-[2000] bg-black/70 flex items-center justify-center p-4"
      data-testid="settings-overlay"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="panel w-full max-w-md panel-in"
        onClick={(e) => e.stopPropagation()}
        data-testid="settings-dialog"
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-[#1E2535]">
          <div>
            <div className="mono text-[10px] uppercase tracking-[0.18em] text-[#5C667A]">
              CONFIG
            </div>
            <div className="text-[14px]">Settings</div>
          </div>
          <button
            onClick={() => onOpenChange(false)}
            className="text-[#8B95A5] hover:text-white"
            data-testid="settings-close"
          >
            <X size={16} />
          </button>
        </div>
        <div className="p-5 space-y-4">
          <label className="block">
            <div className="label-overline mb-2">API Base URL</div>
            <input
              data-testid="settings-api-url"
              value={api}
              onChange={(e) => setApi(e.target.value)}
              placeholder="http://127.0.0.1:8000"
              className="mono w-full bg-transparent border border-[#1E2535] focus:border-[#00C2FF] outline-none px-3 py-2 text-sm text-white placeholder:text-[#5C667A]"
              style={{ borderRadius: 0 }}
            />
            <div className="mono text-[10px] text-[#5C667A] mt-1.5">
              Used for /api/v1/score, /api/v1/explanation, /api/v1/heatmap, etc.
            </div>
          </label>

          <label className="block">
            <div className="label-overline mb-2">Default User Type</div>
            <select
              data-testid="settings-user-type"
              value={ut}
              onChange={(e) => setUt(e.target.value)}
              className="mono w-full bg-[#0A0E1A] border border-[#1E2535] focus:border-[#00C2FF] outline-none px-3 py-2 text-sm text-white"
              style={{ borderRadius: 0 }}
            >
              {USER_TYPES.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="flex items-center justify-end gap-2 p-4 border-t border-[#1E2535]">
          <button
            onClick={() => onOpenChange(false)}
            className="px-4 py-2 text-[12px] text-[#8B95A5] border border-[#1E2535] hover:bg-[#131A2B]"
            style={{ borderRadius: 0 }}
            data-testid="settings-cancel"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="mono px-4 py-2 text-[12px] font-medium"
            style={{
              background: "#00C2FF",
              color: "#0A0E1A",
              borderRadius: 0,
            }}
            data-testid="settings-save"
          >
            SAVE CONFIG
          </button>
        </div>
      </div>
    </div>
  );
};

export default SettingsDialog;
