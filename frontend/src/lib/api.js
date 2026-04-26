import axios from "axios";

const INTERNAL_BASE = process.env.REACT_APP_BACKEND_URL;
export const INTERNAL_API = `${INTERNAL_BASE}/api`;

const STORAGE_KEY = "aotw.settings";

export function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) {
    /* empty */
  }
  return {
    apiBaseUrl: "http://127.0.0.1:8000",
    defaultUserType: "data_center",
  };
}

export function saveSettings(s) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
}

function externalBase() {
  const { apiBaseUrl } = loadSettings();
  return (apiBaseUrl || "http://127.0.0.1:8000").replace(/\/+$/, "");
}

const externalClient = () =>
  axios.create({
    baseURL: externalBase(),
    timeout: 60000,
  });

const internalClient = axios.create({
  baseURL: INTERNAL_API,
  timeout: 30000,
});

function reshapeAuditForPanel(audit) {
  if (!audit || typeof audit !== "object") return audit;

  const topRisks = (audit.top_risks || []).map((risk) => ({
    ...risk,
    field_path: risk.field_path || risk.evidence_paths || [],
  }));

  const nextChecks = (audit.recommended_next_checks || audit.next_checks || []).map(
    (check) => ({
      ...check,
      text: check.text || check.check || "",
    })
  );

  return {
    ...audit,
    feasibility: {
      water: audit?.water_feasibility?.status || audit?.feasibility?.water || "unknown",
      cooling:
        audit?.cooling_feasibility?.status || audit?.feasibility?.cooling || "unknown",
      permit: audit?.permit_feasibility?.status || audit?.feasibility?.permit || "unknown",
    },
    overall: audit?.overall_assessment || audit?.overall || {},
    top_risks: topRisks,
    next_checks: nextChecks,
  };
}

// ---- External backend (real scoring + Claude) ----
export const ext = {
  scoreInvestment: (body) =>
    externalClient()
      .post("/api/v1/score/investment", body)
      .then((r) => r.data),
  explainInvestment: (input) => {
    if (input?.investment_grade_response) {
      return externalClient()
        .post("/api/v1/explanation/investment", {
          investment_grade_response: input.investment_grade_response,
          user_type: input.user_type,
          location_name: input.location_name,
        })
        .then((r) => reshapeAuditForPanel(r.data));
    }

    return externalClient()
      .get("/api/v1/explanation/investment", { params: input })
      .then((r) => reshapeAuditForPanel(r.data));
  },
  heatmap: (body) =>
    externalClient()
      .post("/api/v1/heatmap", body)
      .then((r) => r.data),
  finlandOracle: (body) =>
    externalClient()
      .post("/api/v1/finland/oracle", body)
      .then((r) => r.data),
  legalVesilaki: (body) =>
    externalClient()
      .post("/api/v1/legal/vesilaki", body)
      .then((r) => r.data),
  lineage: (params) =>
    externalClient()
      .get("/api/v1/lineage", { params })
      .then((r) => r.data),
};

// ---- Internal backend (MongoDB persistence) ----
export const internal = {
  listLocations: () => internalClient.get("/locations").then((r) => r.data),
  saveLocation: (body) =>
    internalClient.post("/locations", body).then((r) => r.data),
  deleteLocation: (id) =>
    internalClient.delete(`/locations/${id}`).then((r) => r.data),

  listLeaderboard: () =>
    internalClient.get("/leaderboard").then((r) => r.data),
  addLeaderboard: (body) =>
    internalClient.post("/leaderboard", body).then((r) => r.data),
  deleteLeaderboardEntry: (id) =>
    internalClient.delete(`/leaderboard/${id}`).then((r) => r.data),
  clearLeaderboard: () =>
    internalClient.delete("/leaderboard").then((r) => r.data),
};
