import { useEffect, useState, useCallback, useRef } from "react";
import {
  Database, Search, Download, Eye, Share2, Lock, Trash2, Briefcase,
  AlertCircle, FileText, X, SlidersHorizontal,
} from "lucide-react";
import { resumeDbApi, jobsApi, apiErr } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Button, Modal, Skeleton, EmptyState, Spinner, SourceBadge } from "@/components/ui";
import ResumeView from "@/components/ResumeView";
import { CANDIDATE_SOURCES } from "@/config/sources";
import { fmtDate } from "@/constants";
import { toast } from "sonner";

const PAGE_SIZE = 25;

// Trigger a browser download from a blob response (same approach as the
// candidate resume download — server-generated PDF, not the print dialog).
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Detail drawer: formatted resume (reuses ResumeView), sharing, move-to-job
// ---------------------------------------------------------------------------

function DetailModal({ recordId, onClose, onChanged }) {
  const [record, setRecord] = useState(null);
  const [loading, setLoading] = useState(true);
  const [structured, setStructured] = useState(null);
  const [structuring, setStructuring] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await resumeDbApi.get(recordId);
      setRecord(r.data);
      setStructured(r.data.resume_structured || null);
    } catch (err) {
      toast.error(apiErr(err, "Couldn't open this resume."));
      onClose();
    } finally {
      setLoading(false);
    }
  }, [recordId, onClose]);
  useEffect(() => { load(); }, [load]);

  // Generate the formatted view once (cached server-side thereafter).
  const buildFormatted = async () => {
    if (structured || structuring) return;
    setStructuring(true);
    try {
      const r = await resumeDbApi.structure(recordId);
      setStructured(r.data.structured);
      if (!r.data.cached) onChanged?.(); // skills/experience backfilled → refresh list
    } catch (err) {
      toast.error(apiErr(err, "Could not build the formatted resume."));
    } finally {
      setStructuring(false);
    }
  };

  const download = async () => {
    setDownloading(true);
    try {
      const res = await resumeDbApi.resumePdf(recordId);
      downloadBlob(res.data, `${record?.name || "resume"} - Resume.pdf`);
    } catch (err) {
      toast.error(apiErr(err, "Couldn't download the resume."));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Modal
      open onClose={onClose} width="max-w-3xl"
      title={loading ? "Resume" : (record?.name || "Resume")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Close</Button>
          {record && (
            <Button onClick={download} disabled={downloading} data-testid="rdb-download">
              <Download size={15} /> {downloading ? "Preparing…" : "Download PDF"}
            </Button>
          )}
        </>
      }
    >
      {loading ? (
        <div className="space-y-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : structured ? (
        <ResumeView data={structured} />
      ) : (
        <div className="text-center py-8">
          <FileText size={30} className="mx-auto text-gray-300" />
          <p className="text-sm text-gray-600 mt-3">
            Build a clean, consistent formatted view of this resume.
          </p>
          <Button className="mt-4" onClick={buildFormatted} disabled={structuring} data-testid="rdb-build-formatted">
            {structuring ? <><Spinner size={15} /> Building…</> : <><Eye size={15} /> Formatted view</>}
          </Button>
          {record?.resume_text && (
            <details className="mt-5 text-left">
              <summary className="text-xs text-gray-400 cursor-pointer">Show raw extracted text</summary>
              <pre className="mt-2 whitespace-pre-wrap text-xs text-gray-600 bg-gray-50 rounded-lg p-3 max-h-64 overflow-y-auto">
                {record.resume_text}
              </pre>
            </details>
          )}
        </div>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Move-to-job: reuse the existing job/candidate flow, source Internal Database
// ---------------------------------------------------------------------------

function MoveToJobModal({ record, onClose, onDone }) {
  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    jobsApi.list()
      .then((r) => setJobs((r.data || []).filter((j) => j.status !== "closed")))
      .catch(() => toast.error("Couldn't load your jobs."))
      .finally(() => setLoading(false));
  }, []);

  const confirm = async () => {
    if (!jobId) return;
    setSaving(true);
    try {
      await resumeDbApi.moveToJob(record.id, jobId);
      toast.success(`${record.name || "Candidate"} added to the job as “Internal Database”.`);
      onDone?.();
      onClose();
    } catch (err) {
      toast.error(apiErr(err, "Couldn't add this candidate to the job."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open onClose={onClose} width="max-w-md" title={`Add ${record?.name || "candidate"} to a job`}
      footer={<>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button onClick={confirm} disabled={saving || !jobId} data-testid="rdb-move-confirm">
          {saving ? "Adding…" : "Add to job"}
        </Button>
      </>}
    >
      <p className="text-sm text-gray-600 leading-relaxed">
        This reuses the existing resume — no re-upload. The candidate is added with source
        <span className="font-medium"> Internal Database</span> and keeps its already-parsed data.
      </p>
      <label className="text-sm font-medium text-gray-700 mt-4 block">Job</label>
      {loading ? (
        <Skeleton className="h-10 mt-1.5" />
      ) : jobs.length ? (
        <select
          value={jobId} onChange={(e) => setJobId(e.target.value)}
          className="mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm bg-white outline-none focus:border-indigo"
          data-testid="rdb-move-job"
        >
          <option value="">Select a job…</option>
          {jobs.map((j) => <option key={j.id} value={j.id}>{j.title}{j.department ? ` · ${j.department}` : ""}</option>)}
        </select>
      ) : (
        <p className="text-sm text-gray-500 mt-2">You don't have any open jobs to add this candidate to.</p>
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Filter bar
// ---------------------------------------------------------------------------

const EMPTY_FILTERS = { q: "", skills: "", source: "", min_experience: "", uploaded_from: "", uploaded_to: "", shared: "" };

function Filters({ value, onChange, onReset }) {
  const set = (k, v) => onChange({ ...value, [k]: v });
  const inputCls = "w-full rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white outline-none focus:border-indigo focus:ring-2 focus:ring-indigo/15";
  const dirty = Object.values(value).some((v) => v !== "");

  return (
    <div className="sticky top-[var(--topbar-h)] z-10 bg-gray-50 border-b border-gray-200 px-9 py-3">
      <div className="flex flex-wrap items-end gap-2.5">
        <div className="relative flex-1 min-w-[220px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={value.q} onChange={(e) => set("q", e.target.value)}
            placeholder="Search name, email or resume text"
            className={`${inputCls} pl-9`} data-testid="rdb-search"
          />
        </div>
        <input
          value={value.skills} onChange={(e) => set("skills", e.target.value)}
          placeholder="Skills (comma-separated)"
          className={`${inputCls} w-[190px]`} data-testid="rdb-skills"
        />
        <select value={value.source} onChange={(e) => set("source", e.target.value)} className={`${inputCls} w-[170px]`} data-testid="rdb-source">
          <option value="">Any source</option>
          {CANDIDATE_SOURCES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
        </select>
        <input
          type="number" min="0" value={value.min_experience} onChange={(e) => set("min_experience", e.target.value)}
          placeholder="Min yrs" className={`${inputCls} w-[92px]`} data-testid="rdb-min-exp"
        />
        <select value={value.shared} onChange={(e) => set("shared", e.target.value)} className={`${inputCls} w-[140px]`} data-testid="rdb-shared">
          <option value="">Shared & private</option>
          <option value="true">Shared only</option>
          <option value="false">Private only</option>
        </select>
        <div className="flex items-center gap-1.5">
          <input type="date" value={value.uploaded_from} onChange={(e) => set("uploaded_from", e.target.value)} className={`${inputCls} w-[150px]`} title="Uploaded from" data-testid="rdb-from" />
          <span className="text-gray-400 text-xs">–</span>
          <input type="date" value={value.uploaded_to} onChange={(e) => set("uploaded_to", e.target.value)} className={`${inputCls} w-[150px]`} title="Uploaded to" data-testid="rdb-to" />
        </div>
        {dirty && (
          <Button variant="ghost" className="!px-2.5" onClick={onReset} title="Clear filters" data-testid="rdb-reset">
            <X size={15} className="text-gray-400" /> Clear
          </Button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ResumeDB() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [detailId, setDetailId] = useState(null);
  const [moveTarget, setMoveTarget] = useState(null);
  const [busyId, setBusyId] = useState(null);

  // Debounce filter changes so typing doesn't fire a request per keystroke.
  const debounce = useRef(null);

  const load = useCallback(async (nextOffset = 0) => {
    setLoading(true);
    setLoadError(false);
    try {
      const r = await resumeDbApi.list({ ...filters, limit: PAGE_SIZE, offset: nextOffset });
      setRows(r.data.results || []);
      setTotal(r.data.total || 0);
      setOffset(nextOffset);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => load(0), 300);
    return () => debounce.current && clearTimeout(debounce.current);
  }, [load]);

  const toggleShare = async (row) => {
    setBusyId(row.id);
    try {
      await resumeDbApi.setShared(row.id, !row.shared);
      setRows((rs) => rs.map((r) => (r.id === row.id ? { ...r, shared: !r.shared } : r)));
      toast.success(!row.shared ? "Shared with your organisation" : "Set back to private");
    } catch (err) {
      toast.error(apiErr(err, "Couldn't change sharing."));
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (row) => {
    if (!window.confirm(`Remove ${row.name || row.email || "this resume"} from the Resume DB? Jobs it was already added to keep their copy.`)) return;
    setBusyId(row.id);
    try {
      await resumeDbApi.remove(row.id);
      toast.success("Removed from Resume DB");
      load(offset);
    } catch (err) {
      toast.error(apiErr(err, "Couldn't remove this resume."));
    } finally {
      setBusyId(null);
    }
  };

  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + PAGE_SIZE, total);

  return (
    <Layout>
      <Topbar
        title="Resume DB"
        subtitle="Your organisation's internal resume repository"
      />
      <Filters value={filters} onChange={setFilters} onReset={() => setFilters(EMPTY_FILTERS)} />

      <PageBody fullWidth>
        <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-gray-200 bg-white px-4 py-3 text-xs leading-relaxed text-gray-600">
          <SlidersHorizontal size={14} className="mt-0.5 shrink-0 text-indigo" />
          <p>
            Every resume uploaded through a job lands here automatically. View a formatted copy, download it,
            reuse it on another job (source <span className="font-medium">Internal Database</span>), and share
            with your team. Private resumes are visible only to you and your admins.
          </p>
        </div>

        {loadError ? (
          <Card className="p-6">
            <div className="flex items-start gap-3">
              <AlertCircle size={18} className="mt-0.5 shrink-0 text-coral" />
              <div>
                <div className="font-medium text-gray-800 text-sm">We couldn't load the Resume DB right now.</div>
                <div className="text-sm text-gray-600 mt-0.5">This looks like a connection or server problem.</div>
                <Button variant="secondary" className="mt-3" onClick={() => load(0)} data-testid="rdb-retry">Try again</Button>
              </div>
            </div>
          </Card>
        ) : (
          <Card className="overflow-hidden">
            {loading ? (
              <div className="p-4 space-y-3">{[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-12" />)}</div>
            ) : rows.length ? (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                        <th className="px-4 py-3 font-medium">Candidate</th>
                        <th className="px-4 py-3 font-medium">Skills</th>
                        <th className="px-4 py-3 font-medium">Exp.</th>
                        <th className="px-4 py-3 font-medium">Source</th>
                        <th className="px-4 py-3 font-medium">Uploaded</th>
                        <th className="px-4 py-3 font-medium">Sharing</th>
                        <th className="px-4 py-3 font-medium text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr key={r.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50" data-testid={`rdb-row-${r.id}`}>
                          <td className="px-4 py-3">
                            <button className="text-left" onClick={() => setDetailId(r.id)}>
                              <div className="font-medium text-gray-800 hover:text-indigo">{r.name || "—"}</div>
                              <div className="text-xs text-gray-400">{r.email || "no email"}</div>
                            </button>
                          </td>
                          <td className="px-4 py-3">
                            {r.skills?.length ? (
                              <div className="flex flex-wrap gap-1 max-w-[240px]">
                                {r.skills.slice(0, 4).map((s, i) => (
                                  <span key={i} className="rounded-md bg-gray-100 px-1.5 py-0.5 text-[11px] font-medium text-gray-600">{s}</span>
                                ))}
                                {r.skills.length > 4 && <span className="text-[11px] text-gray-400">+{r.skills.length - 4}</span>}
                              </div>
                            ) : (
                              <span className="text-xs text-gray-300">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-gray-700">{r.experience_years != null ? `${r.experience_years} yr` : "—"}</td>
                          <td className="px-4 py-3"><SourceBadge source={r.source} /></td>
                          <td className="px-4 py-3 text-gray-500 text-xs">{fmtDate(r.uploaded_at)}</td>
                          <td className="px-4 py-3">
                            <button
                              onClick={() => toggleShare(r)} disabled={busyId === r.id}
                              className="inline-flex items-center gap-1.5 text-xs font-medium disabled:opacity-50"
                              data-testid={`rdb-share-${r.id}`}
                              title={r.shared ? "Shared with your org — click to make private" : "Private — click to share with your org"}
                            >
                              {r.shared
                                ? <><Share2 size={13} className="text-green" /> <span className="text-green">Shared</span></>
                                : <><Lock size={13} className="text-gray-400" /> <span className="text-gray-500">Private</span></>}
                            </button>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center justify-end gap-1">
                              <Button variant="ghost" className="!px-2 !py-1.5" onClick={() => setDetailId(r.id)} title="View" data-testid={`rdb-view-${r.id}`}>
                                <Eye size={15} className="text-gray-500" />
                              </Button>
                              <Button variant="ghost" className="!px-2 !py-1.5" onClick={() => setMoveTarget(r)} title="Add to a job" data-testid={`rdb-move-${r.id}`}>
                                <Briefcase size={15} className="text-indigo" />
                              </Button>
                              <Button variant="ghost" className="!px-2 !py-1.5" onClick={() => remove(r)} disabled={busyId === r.id} title="Remove" data-testid={`rdb-remove-${r.id}`}>
                                <Trash2 size={15} className="text-gray-400" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 text-xs text-gray-500">
                  <span data-testid="rdb-count">Showing {pageStart}–{pageEnd} of {total}</span>
                  <div className="flex items-center gap-2">
                    <Button variant="secondary" className="!px-2.5 !py-1" disabled={offset === 0} onClick={() => load(Math.max(0, offset - PAGE_SIZE))}>Previous</Button>
                    <Button variant="secondary" className="!px-2.5 !py-1" disabled={pageEnd >= total} onClick={() => load(offset + PAGE_SIZE)}>Next</Button>
                  </div>
                </div>
              </>
            ) : (
              <EmptyState
                icon={Database}
                title="No resumes match"
                subtitle="Resumes uploaded through your jobs appear here. Try clearing the filters, or upload candidates from a job."
              />
            )}
          </Card>
        )}
      </PageBody>

      {detailId && (
        <DetailModal recordId={detailId} onClose={() => setDetailId(null)} onChanged={() => load(offset)} />
      )}
      {moveTarget && (
        <MoveToJobModal record={moveTarget} onClose={() => setMoveTarget(null)} onDone={() => load(offset)} />
      )}
    </Layout>
  );
}
