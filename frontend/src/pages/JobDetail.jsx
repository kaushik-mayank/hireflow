import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Upload, Sparkles, LayoutGrid, FileText, Activity, Search, Trash2, Eye, ArrowRight, CheckSquare } from "lucide-react";
import { jobsApi, candidatesApi, aiApi, apiErr } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Button, AIButton, ScoreBadge, StageBadge, Avatar, Pill, Skeleton, EmptyState, Spinner } from "@/components/ui";
import { STAGES, fmtDate } from "@/constants";
import { toast } from "sonner";

export default function JobDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [cands, setCands] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("candidates");
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [activity, setActivity] = useState([]);
  const [jdView, setJdView] = useState("original");
  const fileRef = useRef();

  // candidate filters
  const [search, setSearch] = useState("");
  const [stageFilter, setStageFilter] = useState("all");
  const [minScore, setMinScore] = useState(0);
  const [sortBy, setSortBy] = useState("score");
  const [selected, setSelected] = useState([]);

  const loadCands = useCallback(() => {
    candidatesApi.listByJob(id).then((r) => setCands(r.data)).catch(() => {});
  }, [id]);

  useEffect(() => {
    Promise.all([jobsApi.get(id), candidatesApi.listByJob(id)])
      .then(([j, c]) => { setJob(j.data); setCands(c.data); })
      .catch(() => toast.error("Could not load job"))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (tab === "activity") jobsApi.activity(id).then((r) => setActivity(r.data)).catch(() => {});
  }, [tab, id]);

  const handleFiles = async (fileList) => {
    const files = Array.from(fileList).filter((f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"));
    if (files.length === 0) {
      toast.error("Only PDF files are accepted");
      return;
    }
    const tooBig = files.find((f) => f.size > 5 * 1024 * 1024);
    if (tooBig) {
      toast.error(`${tooBig.name} exceeds 5MB`);
      return;
    }
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
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

  let view = cands.filter((c) => {
    const okSearch = (c.name || "").toLowerCase().includes(search.toLowerCase());
    const okStage = stageFilter === "all" || c.stage === stageFilter;
    const okScore = (c.ai_score ?? 0) >= minScore;
    return okSearch && okStage && okScore;
  });
  view.sort((a, b) => {
    if (sortBy === "score") return (b.ai_score ?? -1) - (a.ai_score ?? -1);
    if (sortBy === "name") return (a.name || "").localeCompare(b.name || "");
    return new Date(b.uploaded_at) - new Date(a.uploaded_at);
  });

  if (loading) return <Layout><Topbar title="Loading..." /><PageBody><Skeleton className="h-64 rounded-xl" /></PageBody></Layout>;
  if (!job) return null;

  const jdText = jdView === "enhanced" && job.jd_enhanced ? job.jd_enhanced : job.jd_text;

  return (
    <Layout>
      <Topbar
        title={job.title}
        subtitle={`${job.department || "No dept"} · ${job.openings_needed} opening(s) · ${job.hired_count}/${job.openings_needed} hired`}
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
            <AIButton loading={analyzing} onClick={analyzeAll} data-testid="analyze-all-btn">
              {analyzing ? "Analyzing..." : "Analyze All Candidates"}
            </AIButton>
          </div>
          <div
            className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${dragOver ? "border-indigo bg-indigo-light/40" : "border-gray-200 hover:border-indigo/50"}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files); }}
            onClick={() => fileRef.current?.click()}
            data-testid="upload-zone"
          >
            <input ref={fileRef} type="file" accept="application/pdf" multiple className="hidden" onChange={(e) => handleFiles(e.target.files)} data-testid="upload-input" />
            {uploading ? <Spinner size={22} className="mx-auto text-indigo" /> : <Upload size={22} className="mx-auto text-gray-400" />}
            <p className="text-sm text-gray-700 mt-2 font-medium">{uploading ? "Uploading..." : "Drop PDF resumes here or click to browse"}</p>
            <p className="text-xs text-gray-400 mt-1">Multiple PDFs · max 5MB each</p>
          </div>
        </Card>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-gray-200 mb-4">
          {[["candidates", "Candidates", null], ["jd", "JD Preview", FileText], ["activity", "Activity", Activity]].map(([k, label]) => (
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
                {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
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
                <select onChange={(e) => e.target.value && bulkMove(e.target.value)} className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm bg-white ml-auto" defaultValue="" data-testid="bulk-stage-select">
                  <option value="" disabled>Move to stage...</option>
                  {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
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
                        <span className="font-medium text-gray-800 truncate">{c.name}</span>
                        <ScoreBadge score={c.ai_score} />
                      </div>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(c.matched_skills || []).slice(0, 2).map((s) => <Pill key={s} tone="green">{s}</Pill>)}
                        {(c.missing_skills || []).slice(0, 1).map((s) => <Pill key={s} tone="red">{s}</Pill>)}
                      </div>
                    </div>
                    <StageBadge stage={c.stage} />
                    <div className="flex gap-1">
                      <button onClick={() => navigate(`/candidates/${c.id}`)} className="p-2 text-gray-500 hover:text-indigo hover:bg-indigo-light rounded-lg" title="View profile" data-testid={`cand-view-${c.id}`}><Eye size={16} /></button>
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
            <div className="flex gap-2 mb-4">
              <button onClick={() => setJdView("original")} className={`text-sm px-3 py-1.5 rounded-lg ${jdView === "original" ? "bg-indigo text-white" : "bg-gray-100 text-gray-700"}`} data-testid="jd-original">Original</button>
              <button onClick={() => setJdView("enhanced")} disabled={!job.jd_enhanced} className={`text-sm px-3 py-1.5 rounded-lg disabled:opacity-40 ${jdView === "enhanced" ? "bg-indigo text-white" : "bg-gray-100 text-gray-700"}`} data-testid="jd-enhanced">Enhanced</button>
            </div>
            <pre className="whitespace-pre-wrap font-sans text-sm text-gray-700 leading-relaxed">{jdText || "No job description provided."}</pre>
          </Card>
        )}

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
      </PageBody>
    </Layout>
  );
}
