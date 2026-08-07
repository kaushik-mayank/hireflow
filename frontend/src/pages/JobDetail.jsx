import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Upload, LayoutGrid, FileText, Activity, Search, Trash2, Eye, ArrowRight, CheckSquare, Users } from "lucide-react";
import { jobsApi, candidatesApi, aiApi, assignmentsApi, orgsApi, apiErr } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Button, AIButton, ScoreBadge, StageBadge, Avatar, Pill, Skeleton, EmptyState, Spinner, SourceBadge, Modal } from "@/components/ui";
import { STAGES, fmtDate } from "@/constants";
import { CANDIDATE_SOURCES } from "@/config/sources";
import AssignmentPanel from "@/components/AssignmentPanel";
import { toast } from "sonner";

// Accepted resume file types (kept in step with the backend allow-list).
const ACCEPTED_EXTS = /\.(pdf|docx|doc|txt|png|jpe?g|webp)$/i;
const ACCEPT_ATTR = ".pdf,.docx,.doc,.txt,.png,.jpg,.jpeg,.webp";

export default function JobDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [cands, setCands] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("candidates");
  const [uploading, setUploading] = useState(false);
  const [source, setSource] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [activity, setActivity] = useState([]);
  const [jdView, setJdView] = useState("original");
  // Recruiter personal-JD editor (only shown when access_scope === "assigned"
  // and the caller has can_edit_jd).
  const [jdEdit, setJdEdit] = useState(false);
  const [jdDraft, setJdDraft] = useState("");
  const [savingJd, setSavingJd] = useState(false);
  const fileRef = useRef();

  // candidate filters
  const [search, setSearch] = useState("");
  const [stageFilter, setStageFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [sourcedByFilter, setSourcedByFilter] = useState("all"); // manager-only: which teammate sourced
  const [minScore, setMinScore] = useState(0);
  const [sortBy, setSortBy] = useState("score");
  const [selected, setSelected] = useState([]);
  const [members, setMembers] = useState([]); // org teammates, for the sourced-by filter (managers)

  const loadCands = useCallback(() => {
    candidatesApi.listByJob(id).then((r) => setCands(r.data)).catch(() => {});
  }, [id]);

  // Single navigation handler shared by the candidate name and the Eye icon so
  // both open the same profile page without duplicating the route.
  const openCandidate = useCallback((cid) => navigate(`/candidates/${cid}`), [navigate]);

  useEffect(() => {
    Promise.all([jobsApi.get(id), candidatesApi.listByJob(id)])
      .then(([j, c]) => { setJob(j.data); setCands(c.data); })
      .catch(() => toast.error("Could not load job"))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (tab === "activity") jobsApi.activity(id).then((r) => setActivity(r.data)).catch(() => {});
  }, [tab, id]);

  // A manager can filter candidates by which teammate sourced them, so load the
  // org's members once we know the caller is a manager on this job.
  useEffect(() => {
    if (job?.access_scope === "manager") orgsApi.members().then((r) => setMembers(r.data)).catch(() => {});
  }, [job?.access_scope]);

  const handleFiles = async (fileList) => {
    // Source is mandatory — block the upload until one is chosen.
    if (!source) {
      toast.error("Please choose where these candidates came from before uploading");
      return;
    }
    const files = Array.from(fileList).filter((f) => ACCEPTED_EXTS.test(f.name));
    if (files.length === 0) {
      toast.error("Accepted files: PDF, Word (DOCX/DOC), images (PNG/JPG) or TXT");
      return;
    }
    const tooBig = files.find((f) => f.size > 5 * 1024 * 1024);
    if (tooBig) {
      toast.error(`${tooBig.name} exceeds 5MB`);
      return;
    }
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    // Captured at upload so Reports can show which channels actually convert.
    fd.append("source", source);
    setUploading(true);
    try {
      const r = await candidatesApi.upload(id, fd);
      toast.success(`${r.data.count} resume(s) uploaded`);
      loadCands();
      jobsApi.get(id).then((j) => setJob(j.data));
    } catch (err) {
      toast.error(apiErr(err, "Upload failed"));
    } finally {
      setUploading(false);
    }
  };

  const analyzeAll = async () => {
    if (!job?.jd_text) { toast.error("Add a job description first"); return; }
    setAnalyzing(true);
    try {
      const r = await aiApi.rank(id, false);
      toast.success(r.data.count ? `${r.data.count} candidate(s) analyzed by AI` : "No new candidates to analyze");
      loadCands();
    } catch (err) {
      toast.error(apiErr(err, "AI analysis failed"));
    } finally {
      setAnalyzing(false);
    }
  };

  const removeCand = async (cid) => {
    try { await candidatesApi.remove(cid); toast.success("Candidate removed"); loadCands(); }
    catch (err) { toast.error(apiErr(err)); }
  };

  const bulkMove = async (stage) => {
    if (!selected.length) return;
    try {
      await candidatesApi.bulkStage({ candidate_ids: selected, stage });
      toast.success(`${selected.length} moved to ${stage}`);
      setSelected([]); loadCands();
    } catch (err) { toast.error(apiErr(err)); }
  };

  const toggleSel = (cid) => setSelected((s) => (s.includes(cid) ? s.filter((x) => x !== cid) : [...s, cid]));

  const reloadJob = () => jobsApi.get(id).then((j) => setJob(j.data)).catch(() => {});

  const openJdEditor = () => { setJdDraft(job?.jd_text || ""); setJdEdit(true); };

  const saveJd = async () => {
    setSavingJd(true);
    try {
      await assignmentsApi.setJdOverride(id, { jd_text: jdDraft });
      toast.success("Saved your version of the job description");
      await reloadJob();
      setJdEdit(false);
    } catch (err) {
      toast.error(apiErr(err, "Couldn't save your version"));
    } finally {
      setSavingJd(false);
    }
  };

  const resetJd = async () => {
    try {
      await assignmentsApi.clearJdOverride(id);
      toast.success("Reverted to the team's version");
      await reloadJob();
    } catch (err) {
      toast.error(apiErr(err, "Couldn't reset your version"));
    }
  };

  let view = cands.filter((c) => {
    const okSearch = (c.name || "").toLowerCase().includes(search.toLowerCase());
    const okStage = stageFilter === "all" || c.stage === stageFilter;
    const okSource = sourceFilter === "all" || c.source === sourceFilter;
    const okSourcedBy = sourcedByFilter === "all" || c.sourced_by === sourcedByFilter;
    const okScore = (c.ai_score ?? 0) >= minScore;
    return okSearch && okStage && okSource && okSourcedBy && okScore;
  });
  view.sort((a, b) => {
    if (sortBy === "score") return (b.ai_score ?? -1) - (a.ai_score ?? -1);
    if (sortBy === "name") return (a.name || "").localeCompare(b.name || "");
    return new Date(b.uploaded_at) - new Date(a.uploaded_at);
  });

  if (loading) return <Layout><Topbar title="Loading..." /><PageBody><Skeleton className="h-64 rounded-xl" /></PageBody></Layout>;
  if (!job) return null;

  const jdText = jdView === "enhanced" && job.jd_enhanced ? job.jd_enhanced : job.jd_text;

  // Manager sees the org job with a Team tab; a recruiter sees their assigned
  // view and — with can_edit_jd — a personal JD editor. (Backend supplies
  // access_scope, jd_source and effective_permissions on the job.)
  const isManager = job.access_scope === "manager";
  const isAssigned = job.access_scope === "assigned";
  const canEditMyJd = isAssigned && Boolean(job.effective_permissions?.can_edit_jd);
  const isPersonalJd = job.jd_source === "personal";
  const tabs = [
    ["candidates", "Candidates", null],
    ["jd", "JD Preview", FileText],
    ...(isManager ? [["team", "Team", Users]] : []),
    ["activity", "Activity", Activity],
  ];

  // Effective permissions for the caller on this job (managers get all true).
  // Undefined flags default to allowed so legacy responses never lock anyone out.
  const perms = job.effective_permissions || {};
  const can = (flag) => perms[flag] !== false;
  const canUpload = can("can_upload_candidates");
  const canUseAI = can("can_use_ai");
  const canMove = can("can_move_stage");
  const NO_PERM = "Your admin hasn't given you this permission on this job.";

  // Default pipeline plus any extra stages this job's admin added (L1/L2/…).
  const effectiveStages = [...STAGES, ...(job.custom_stages || [])];
  // Map a teammate id → display name, for the manager-only "sourced by" filter/label.
  const memberName = (uid) => {
    const m = members.find((x) => x.id === uid);
    return m ? (m.name || m.email) : null;
  };
  const subtitleParts = [
    job.hiring_for ? `Hiring for ${job.hiring_for}` : null,
    job.department || "No dept",
    `${job.openings_needed} opening(s)`,
    `${job.hired_count}/${job.openings_needed} hired`,
  ].filter(Boolean);

  return (
    <Layout>
      <Topbar
        title={job.title}
        subtitle={subtitleParts.join(" · ")}
        actions={<>
          <Button variant="ghost" onClick={() => navigate("/jobs")}><ArrowLeft size={16} /> Back</Button>
          <Button onClick={() => navigate(`/jobs/${id}/board`)} data-testid="open-board-btn"><LayoutGrid size={16} /> Kanban Board</Button>
        </>}
      />
      <PageBody>
        {/* Upload zone */}
        <Card className="p-5 mb-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-800">Upload Resumes</h3>
            <AIButton
              loading={analyzing}
              onClick={analyzeAll}
              disabled={!canUseAI}
              title={canUseAI ? undefined : NO_PERM}
              data-testid="analyze-all-btn"
            >
              {analyzing ? "Analyzing..." : "Analyze All Candidates"}
            </AIButton>
          </div>

          {/* Mandatory: chosen before upload and applied to every file in the
              batch, so Reports/analytics group candidates by a real source. */}
          <div className="mb-3">
            <label htmlFor="upload-source" className="text-xs font-medium text-gray-700">
              Candidate source <span className="text-coral">*</span>
            </label>
            <select
              id="upload-source"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className={`mt-1 block w-full sm:w-72 rounded-lg border px-3 py-2 text-sm bg-white outline-none focus:border-indigo focus:ring-2 focus:ring-indigo/20 ${source ? "border-gray-200" : "border-coral/60"}`}
              data-testid="upload-source"
            >
              <option value="" disabled>Select where they came from…</option>
              {CANDIDATE_SOURCES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </div>

          <div
            className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
              !canUpload
                ? "border-gray-200 bg-gray-50 opacity-70 cursor-not-allowed"
                : `cursor-pointer ${dragOver ? "border-indigo bg-indigo-light/40" : "border-gray-200 hover:border-indigo/50"}`
            }`}
            onDragOver={(e) => { e.preventDefault(); if (canUpload) setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); if (canUpload) handleFiles(e.dataTransfer.files); }}
            onClick={() => canUpload && fileRef.current?.click()}
            title={canUpload ? undefined : NO_PERM}
            data-testid="upload-zone"
          >
            <input ref={fileRef} type="file" accept={ACCEPT_ATTR} multiple className="hidden" onChange={(e) => handleFiles(e.target.files)} disabled={!canUpload} data-testid="upload-input" />
            {uploading ? <Spinner size={22} className="mx-auto text-indigo" /> : <Upload size={22} className="mx-auto text-gray-400" />}
            {canUpload ? (
              <>
                <p className="text-sm text-gray-700 mt-2 font-medium">{uploading ? "Uploading..." : "Drop resumes here or click to browse"}</p>
                <p className="text-xs text-gray-400 mt-1">PDF, Word, images or text · multiple · max 5MB each</p>
              </>
            ) : (
              <>
                <p className="text-sm text-gray-700 mt-2 font-medium">Adding candidates isn't enabled for you</p>
                <p className="text-xs text-gray-400 mt-1">Ask your admin to give you upload access on this job.</p>
              </>
            )}
          </div>
        </Card>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-gray-200 mb-4">
          {tabs.map(([k, label]) => (
            <button key={k} onClick={() => setTab(k)} className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === k ? "border-indigo text-indigo" : "border-transparent text-gray-600 hover:text-gray-800"}`} data-testid={`tab-${k}`}>
              {label} {k === "candidates" && <span className="text-xs text-gray-400">({cands.length})</span>}
            </button>
          ))}
        </div>

        {tab === "candidates" && (
          <>
            <div className="flex flex-wrap items-center gap-3 mb-4">
              <div className="relative flex-1 min-w-[180px] max-w-xs">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name..." className="w-full rounded-lg border border-gray-200 pl-9 pr-3 py-2 text-sm bg-white outline-none focus:border-indigo" data-testid="cand-search" />
              </div>
              <select value={stageFilter} onChange={(e) => setStageFilter(e.target.value)} className="rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white outline-none" data-testid="cand-stage-filter">
                <option value="all">All Stages</option>
                {effectiveStages.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} className="rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white outline-none" data-testid="cand-source-filter">
                <option value="all">All Sources</option>
                {CANDIDATE_SOURCES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
              </select>
              {isManager && members.length > 0 && (
                <select value={sourcedByFilter} onChange={(e) => setSourcedByFilter(e.target.value)} className="rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white outline-none" data-testid="cand-sourcedby-filter">
                  <option value="all">Sourced by: anyone</option>
                  {members.filter((m) => m.status !== "approved").map((m) => <option key={m.id} value={m.id}>{m.name || m.email}</option>)}
                </select>
              )}
              <div className="flex items-center gap-2 text-sm text-gray-600">
                Min score <input type="range" min="0" max="100" value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} className="accent-indigo" data-testid="cand-score-slider" /> <span className="w-7 font-medium">{minScore}</span>
              </div>
              <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white outline-none ml-auto" data-testid="cand-sort">
                <option value="score">Sort: Score</option>
                <option value="name">Sort: Name</option>
                <option value="date">Sort: Date</option>
              </select>
            </div>

            {selected.length > 0 && (
              <div className="flex items-center gap-3 mb-3 bg-indigo-light/50 rounded-lg px-4 py-2.5" data-testid="bulk-bar">
                <CheckSquare size={16} className="text-indigo" />
                <span className="text-sm text-gray-700 font-medium">{selected.length} selected</span>
                <select
                  onChange={(e) => e.target.value && bulkMove(e.target.value)}
                  disabled={!canMove}
                  title={canMove ? undefined : NO_PERM}
                  className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm bg-white ml-auto disabled:opacity-50 disabled:cursor-not-allowed"
                  defaultValue=""
                  data-testid="bulk-stage-select"
                >
                  <option value="" disabled>{canMove ? "Move to stage..." : "Moving not enabled"}</option>
                  {effectiveStages.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <button onClick={() => setSelected([])} className="text-sm text-gray-500 hover:text-gray-700">Clear</button>
              </div>
            )}

            {view.length ? (
              <div className="space-y-2">
                {view.map((c) => (
                  <Card key={c.id} className="p-3.5 flex items-center gap-3 hover:shadow-card transition-shadow" data-testid={`cand-row-${c.id}`}>
                    <input type="checkbox" checked={selected.includes(c.id)} onChange={() => toggleSel(c.id)} className="accent-indigo w-4 h-4" data-testid={`cand-check-${c.id}`} />
                    <Avatar name={c.name} size={38} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => openCandidate(c.id)}
                          className="font-medium text-gray-800 truncate hover:text-indigo hover:underline text-left"
                          title="View profile"
                          data-testid={`cand-name-${c.id}`}
                        >
                          {c.name}
                        </button>
                        <ScoreBadge score={c.ai_score} />
                      </div>
                      <div className="flex flex-wrap items-center gap-1 mt-1">
                        <SourceBadge source={c.source} />
                        {isManager && c.sourced_by && memberName(c.sourced_by) && (
                          <span className="text-[11px] text-gray-400">by {memberName(c.sourced_by)}</span>
                        )}
                        {(c.matched_skills || []).slice(0, 2).map((s) => <Pill key={s} tone="green">{s}</Pill>)}
                        {(c.missing_skills || []).slice(0, 1).map((s) => <Pill key={s} tone="red">{s}</Pill>)}
                      </div>
                    </div>
                    <StageBadge stage={c.stage} />
                    <div className="flex gap-1">
                      <button onClick={() => openCandidate(c.id)} className="p-2 text-gray-500 hover:text-indigo hover:bg-indigo-light rounded-lg" title="View profile" data-testid={`cand-view-${c.id}`}><Eye size={16} /></button>
                      <button onClick={() => removeCand(c.id)} className="p-2 text-gray-500 hover:text-coral hover:bg-coral-light rounded-lg" title="Delete" data-testid={`cand-delete-${c.id}`}><Trash2 size={16} /></button>
                    </div>
                  </Card>
                ))}
              </div>
            ) : (
              <Card><EmptyState icon={Upload} title="No candidates yet" subtitle="Upload PDF resumes above to get started, then run AI analysis." /></Card>
            )}
          </>
        )}

        {tab === "jd" && (
          <Card className="p-6">
            {isAssigned && isPersonalJd && job.jd_org_updated && (
              <div className="mb-4 flex items-start gap-2.5 rounded-lg bg-amber-light/60 px-4 py-3 text-sm text-[#92400e]" data-testid="jd-updated-notice">
                <span>Your admin updated the shared job description after you made your version. Your AI still uses your version — reset to the team version below if you want their latest.</span>
              </div>
            )}
            {isAssigned && (
              <div className="flex flex-wrap items-center gap-2 mb-4">
                <Pill tone={isPersonalJd ? "amber" : "gray"}>{isPersonalJd ? "Your version" : "Team version"}</Pill>
                <span className="text-xs text-gray-500">
                  {isPersonalJd ? "Your AI runs use this personal version." : "This is the shared job description."}
                </span>
                {canEditMyJd && (
                  <Button variant="secondary" className="!py-1.5 ml-auto" onClick={openJdEditor} data-testid="jd-edit-open">
                    {isPersonalJd ? "Edit my version" : "Make my own version"}
                  </Button>
                )}
                {isPersonalJd && (
                  <Button variant="ghost" className="!py-1.5" onClick={resetJd} data-testid="jd-reset">Reset to team version</Button>
                )}
              </div>
            )}
            <div className="flex gap-2 mb-4">
              <button onClick={() => setJdView("original")} className={`text-sm px-3 py-1.5 rounded-lg ${jdView === "original" ? "bg-indigo text-white" : "bg-gray-100 text-gray-700"}`} data-testid="jd-original">Original</button>
              <button onClick={() => setJdView("enhanced")} disabled={!job.jd_enhanced} className={`text-sm px-3 py-1.5 rounded-lg disabled:opacity-40 ${jdView === "enhanced" ? "bg-indigo text-white" : "bg-gray-100 text-gray-700"}`} data-testid="jd-enhanced">Enhanced</button>
            </div>
            <pre className="whitespace-pre-wrap font-sans text-sm text-gray-700 leading-relaxed">{jdText || "No job description provided."}</pre>
          </Card>
        )}

        {tab === "team" && isManager && <AssignmentPanel jobId={id} />}

        {tab === "activity" && (
          <Card className="p-2">
            {activity.length ? activity.map((t) => (
              <div key={t.id} className="flex items-start gap-3 p-3 border-b border-gray-100 last:border-0" data-testid={`activity-${t.id}`}>
                <ArrowRight size={15} className="text-gray-400 mt-0.5" />
                <div className="text-sm text-gray-700">
                  <span className="font-medium">{t.candidate_name}</span> moved {t.from_stage ? `from ${t.from_stage} ` : ""}to <span className="font-medium">{t.to_stage}</span>
                  <span className="text-gray-400"> by {t.moved_by} · {fmtDate(t.moved_at)}</span>
                </div>
              </div>
            )) : <EmptyState icon={Activity} title="No activity yet" subtitle="Stage changes will appear here." />}
          </Card>
        )}

        <Modal
          open={jdEdit}
          onClose={() => setJdEdit(false)}
          title="Edit your version of the job description"
          width="max-w-2xl"
          footer={<>
            <Button variant="secondary" onClick={() => setJdEdit(false)}>Cancel</Button>
            <Button onClick={saveJd} disabled={savingJd} data-testid="jd-edit-save">{savingJd ? "Saving…" : "Save my version"}</Button>
          </>}
        >
          <p className="text-xs text-gray-500 mb-3 leading-relaxed">
            Only you see this version, and your AI ranking and screening use it. The team's original job description
            stays unchanged.
          </p>
          <textarea
            value={jdDraft}
            onChange={(e) => setJdDraft(e.target.value)}
            rows={14}
            className="w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-indigo focus:ring-2 focus:ring-indigo/20 font-sans leading-relaxed"
            placeholder="Paste or write your version of the job description…"
            data-testid="jd-edit-text"
          />
        </Modal>
      </PageBody>
    </Layout>
  );
}
