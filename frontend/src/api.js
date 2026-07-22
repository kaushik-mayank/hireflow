import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const client = axios.create({ baseURL: API });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("hireflow_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response && err.response.status === 401) {
      localStorage.removeItem("hireflow_token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);

export const apiErr = (err, fallback = "Something went wrong") =>
  err?.response?.data?.detail || fallback;

// ---- Auth ----
export const authApi = {
  signup: (data) => client.post("/auth/signup", data),
  login: (data) => client.post("/auth/login", data),
  // Exchanges a verified Firebase ID token for this app's own JWT.
  firebase: (data) => client.post("/auth/firebase", data),
  me: () => client.get("/auth/me"),
};

// ---- Jobs ----
export const jobsApi = {
  list: () => client.get("/jobs"),
  create: (data) => client.post("/jobs", data),
  get: (id) => client.get(`/jobs/${id}`),
  update: (id, data) => client.put(`/jobs/${id}`, data),
  remove: (id) => client.delete(`/jobs/${id}`),
  activity: (id) => client.get(`/jobs/${id}/activity`),
};

// ---- Candidates ----
export const candidatesApi = {
  upload: (jobId, formData, onProgress) =>
    client.post(`/candidates/upload/${jobId}`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: onProgress,
    }),
  listByJob: (jobId) => client.get(`/candidates/job/${jobId}`),
  get: (id) => client.get(`/candidates/${id}`),
  updateStage: (id, data) => client.put(`/candidates/${id}/stage`, data),
  bulkStage: (data) => client.put(`/candidates/bulk-stage`, data),
  addNote: (id, note) => client.post(`/candidates/${id}/note`, { note }),
  remove: (id) => client.delete(`/candidates/${id}`),
};

// ---- AI ----
export const aiApi = {
  rank: (jobId, reanalyze = false) => client.post("/ai/rank", { job_id: jobId, reanalyze }),
  enhanceJD: (jd_text, title) => client.post("/ai/enhance-jd", { jd_text, title }),
  questions: (candidate_id) => client.post("/ai/questions", { candidate_id }),
  email: (candidate_id, email_type) => client.post("/ai/email", { candidate_id, email_type }),
  summary: (candidate_id) => client.post("/ai/summary", { candidate_id }),
  compare: (a, b) => client.post("/ai/compare", { candidate_id_a: a, candidate_id_b: b }),
  pipelineHealth: () => client.post("/ai/pipeline-health"),
};

// ---- Dashboard ----
export const dashboardApi = {
  get: () => client.get("/dashboard"),
};

// ---- Admin ----
export const adminApi = {
  dashboard: () => client.get("/admin/dashboard"),
  users: () => client.get("/admin/users"),
  setStatus: (id, is_active) => client.put(`/admin/users/${id}/status`, { is_active }),
  // No setRole: roles are decided by the server-side admin allowlist only.
  resumes: (page = 1, page_size = 50) => client.get(`/admin/resumes?page=${page}&page_size=${page_size}`),
  resumeDetail: (id) => client.get(`/admin/resumes/${id}`),
  analytics: () => client.get("/admin/analytics"),
  aiUsage: (page = 1, page_size = 50) => client.get(`/admin/ai-usage?page=${page}&page_size=${page_size}`),
};

// ---- Reports ----
export const reportsApi = {
  get: () => client.get("/reports"),
};

// ---- Feedback / Support ----
export const feedbackApi = {
  submit: (data) => client.post("/feedback", data),
  mine: () => client.get("/feedback/mine"),
  adminList: (params = {}) => {
    const q = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
    ).toString();
    return client.get(`/feedback/admin${q ? `?${q}` : ""}`);
  },
  setStatus: (id, status) => client.put(`/feedback/admin/${id}/status`, { status }),
};

export default client;
