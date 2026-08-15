import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Search, Briefcase, Users, Calendar, CalendarClock, Target, Eye, Pause, Play, Ban, UserRound } from "lucide-react";
import { jobsApi, apiErr } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Button, ProgressBar, Skeleton, EmptyState, Modal } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { fmtDate } from "@/constants";
import { toast } from "sonner";

export default function Jobs() {
  const { user } = useAuth();
  // Everyone can create a job (a manager/sub-admin makes a team job; a normal
  // user makes a personal one). The admin tier also sees every team job.
  const isManager = (user?.org_role || "manager") === "manager";
  const caps = user?.admin_permissions || [];
  // Pause/reactivate is owner-or-manager; close is additionally available to a
  // Sub-Admin with `delete_jobs` on a team job — mirrors the server rules so the
  // UI never offers an action the backend rejects.
  const canPause = (j) => j.status !== "closed" && (isManager || j.created_by === user?.id);
  const canClose = (j) =>
    j.status !== "closed" &&
    (isManager || j.created_by === user?.id || (j.origin !== "personal" && caps.includes("delete_jobs")));
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [companyFilter, setCompanyFilter] = useState(""); // "hiring for" combo (type or pick)
  const [closeTarget, setCloseTarget] = useState(null);   // job pending a close confirmation
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    jobsApi.list().then((r) => setJobs(r.data)).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const toggleStatus = async (e, job) => {
    e.stopPropagation();
    // Pause ↔ reactivate. A paused job is temporary (not closed, not deleted).
    const next = job.status === "active" ? "paused" : "active";
    try {
      await jobsApi.update(job.id, { status: next });
      toast.success(`Job ${next === "active" ? "reactivated" : "paused"}`);
      load();
    } catch (err) {
      toast.error(apiErr(err));
    }
  };

  const closeJob = (e, job) => {
    e.stopPropagation();
    setCloseTarget(job); // open the confirmation modal (no browser confirm popup)
  };

  const doClose = async () => {
    if (!closeTarget) return;
    // Closing is terminal: the job stays visible in the list marked "Closed" —
    // it is NOT deleted and its data is preserved.
    try {
      await jobsApi.update(closeTarget.id, { status: "closed" });
      toast.success("Job closed");
      setCloseTarget(null);
      load();
    } catch (err) {
      toast.error(apiErr(err));
    }
  };

  const companies = [...new Set(jobs.map((j) => j.hiring_for).filter(Boolean))].sort();
  const filtered = jobs.filter((j) => {
    const okStatus = statusFilter === "all" || j.status === statusFilter;
    const okSearch = j.title.toLowerCase().includes(search.toLowerCase());
    const okCompany = !companyFilter.trim() || (j.hiring_for || "").toLowerCase().includes(companyFilter.trim().toLowerCase());
    return okStatus && okSearch && okCompany;
  });

  const statusColor = (s) => (s === "active" ? "text-green bg-green-light" : s === "paused" ? "text-amber bg-amber-light" : "text-gray-600 bg-gray-100");

  return (
    <Layout>
      <Topbar
        title="Jobs"
        subtitle={isManager ? "Manage your open roles and hiring quotas" : "Roles assigned to you, plus your own"}
        actions={<Button onClick={() => navigate("/jobs/create")} data-testid="jobs-create-btn"><Plus size={16} /> {isManager ? "Create New Job" : "Create My Job"}</Button>}
      />
      <PageBody>
        {/* Filters stay pinned below the Topbar while the jobs list scrolls. */}
        <div className="sticky z-10 bg-gray-50 py-3 mb-2 flex items-center gap-3" style={{ top: "var(--topbar-h, 0px)" }}>
          <div className="relative flex-1 max-w-xs">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by title..."
              className="w-full rounded-lg border border-gray-200 pl-9 pr-3 py-2 text-sm focus:border-indigo focus:ring-2 focus:ring-indigo/20 outline-none bg-white"
              data-testid="jobs-search"
            />
          </div>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white outline-none focus:border-indigo" data-testid="jobs-status-filter">
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="closed">Closed</option>
          </select>
          {/* Company/client filter — type to search or pick from the list. */}
          <div className="relative min-w-[190px]">
            <input
              list="jobs-company-list" value={companyFilter} onChange={(e) => setCompanyFilter(e.target.value)}
              placeholder="Hiring for (company)…"
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white outline-none focus:border-indigo"
              data-testid="jobs-company-filter"
            />
            <datalist id="jobs-company-list">
              {companies.map((c) => <option key={c} value={c} />)}
            </datalist>
          </div>
        </div>

        {loading ? (
          <div className="grid md:grid-cols-2 gap-4">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-44 rounded-xl" />)}</div>
        ) : filtered.length ? (
          <div className="grid md:grid-cols-2 gap-4">
            {filtered.map((j) => (
              <Card key={j.id} className="p-5 hover:shadow-card transition-shadow cursor-pointer group" onClick={() => navigate(`/jobs/${j.id}`)} data-testid={`job-card-${j.id}`}>
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-gray-800 group-hover:text-indigo transition-colors">{j.title}</h3>
                    <p className="text-sm text-gray-600 mt-0.5">{j.department || "No department"}</p>
                    {j.hiring_for && <p className="text-xs text-indigo mt-0.5">Hiring for {j.hiring_for}</p>}
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {j.origin === "personal" && <span className="text-[10px] font-semibold rounded-full px-2 py-0.5 bg-indigo-light text-indigo" title="Only you can see this job">Personal</span>}
                    <span className={`text-xs font-medium rounded-full px-2.5 py-1 capitalize ${statusColor(j.status)}`}>{j.status}</span>
                  </div>
                </div>

                <div className="mt-4">
                  <div className="flex items-center justify-between text-xs text-gray-600 mb-1.5">
                    <span>Hiring progress</span>
                    <span className="font-medium">{j.hired_count} / {j.openings_needed} hired</span>
                  </div>
                  <ProgressBar value={j.hired_count} max={j.openings_needed} />
                </div>

                {(j.my_deadline || j.my_targets?.shortlist_target != null || j.my_targets?.sourced_target != null) && (
                  <div className="flex flex-wrap items-center gap-3 mt-3 text-xs">
                    {j.my_deadline && <span className="inline-flex items-center gap-1 text-[#92400e]"><CalendarClock size={13} /> Due {fmtDate(j.my_deadline)}</span>}
                    {j.my_targets?.sourced_target != null && <span className="inline-flex items-center gap-1 text-gray-600"><Target size={13} /> Sourcing target: {j.my_targets.sourced_target}</span>}
                    {j.my_targets?.shortlist_target != null && <span className="inline-flex items-center gap-1 text-gray-600"><Target size={13} /> Shortlisting target: {j.my_targets.shortlist_target}</span>}
                  </div>
                )}

                <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100 text-sm text-gray-600">
                  <span className="flex items-center gap-1.5"><Users size={14} /> {j.candidate_count} candidates</span>
                  <span className="flex items-center gap-1.5"><Calendar size={14} /> {fmtDate(j.created_at)}</span>
                </div>
                {/* Who created the job — from the persisted creator (§6). */}
                {j.created_by_name && (
                  <div className="mt-2 text-xs text-gray-400 flex items-center gap-1.5" data-testid={`job-creator-${j.id}`}>
                    <UserRound size={12} /> Created by {j.created_by_name}
                  </div>
                )}

                <div className="flex gap-2 mt-4">
                  <Button variant="secondary" className="flex-1" onClick={(e) => { e.stopPropagation(); navigate(`/jobs/${j.id}`); }} data-testid={`job-view-${j.id}`}><Eye size={14} /> View</Button>
                  {canPause(j) && (
                    <Button variant="ghost" onClick={(e) => toggleStatus(e, j)} title={j.status === "active" ? "Pause job" : "Reactivate job"} data-testid={`job-toggle-${j.id}`}>
                      {j.status === "active" ? <Pause size={14} /> : <Play size={14} />}
                    </Button>
                  )}
                  {canClose(j) && (
                    <Button variant="ghost" onClick={(e) => closeJob(e, j)} title="Close job" data-testid={`job-close-${j.id}`}>
                      <Ban size={14} className="text-coral" />
                    </Button>
                  )}
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <Card>
            {search || statusFilter !== "all" ? (
              <EmptyState icon={Briefcase} title="No jobs found" subtitle="Try adjusting your filters." />
            ) : isManager ? (
              <EmptyState icon={Briefcase} title="No jobs yet" subtitle="Create your first job to start hiring." action={<Button onClick={() => navigate("/jobs/create")}><Plus size={16} /> Create Job</Button>} />
            ) : (
              <EmptyState icon={Briefcase} title="No jobs yet" subtitle="Roles your admin assigns you appear here — or create your own job, visible only to you." action={<Button onClick={() => navigate("/jobs/create")}><Plus size={16} /> Create My Job</Button>} />
            )}
          </Card>
        )}
      </PageBody>

      <Modal
        open={!!closeTarget}
        onClose={() => setCloseTarget(null)}
        title="Close this job?"
        width="max-w-md"
        footer={<>
          <Button variant="secondary" onClick={() => setCloseTarget(null)} data-testid="close-cancel">Cancel</Button>
          <Button variant="danger" onClick={doClose} data-testid="close-confirm">Close job</Button>
        </>}
      >
        <p className="text-sm text-gray-600 leading-relaxed">
          <span className="font-medium text-gray-800">{closeTarget?.title}</span> will be marked{" "}
          <span className="font-medium">Closed</span>. It stays in your Jobs list and every candidate and record is
          kept, but it stops accepting activity — you won't be able to add candidates, run analysis or change stages.
          You'll still be able to open it and view everything.
        </p>
      </Modal>
    </Layout>
  );
}
