import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Search, Briefcase, Users, Calendar, MoreVertical, Eye, Pause, Play } from "lucide-react";
import { jobsApi, apiErr } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Button, ProgressBar, Skeleton, EmptyState } from "@/components/ui";
import { fmtDate } from "@/constants";
import { toast } from "sonner";

export default function Jobs() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    jobsApi.list().then((r) => setJobs(r.data)).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const toggleStatus = async (e, job) => {
    e.stopPropagation();
    const next = job.status === "active" ? "paused" : "active";
    try {
      await jobsApi.update(job.id, { status: next });
      toast.success(`Job ${next === "active" ? "reactivated" : "paused"}`);
      load();
    } catch (err) {
      toast.error(apiErr(err));
    }
  };

  const filtered = jobs.filter((j) => {
    const okStatus = statusFilter === "all" || j.status === statusFilter;
    const okSearch = j.title.toLowerCase().includes(search.toLowerCase());
    return okStatus && okSearch;
  });

  const statusColor = (s) => (s === "active" ? "text-green bg-green-light" : s === "paused" ? "text-amber bg-amber-light" : "text-gray-600 bg-gray-100");

  return (
    <Layout>
      <Topbar
        title="Jobs"
        subtitle="Manage your open roles and hiring quotas"
        actions={<Button onClick={() => navigate("/jobs/create")} data-testid="jobs-create-btn"><Plus size={16} /> Create New Job</Button>}
      />
      <PageBody>
        <div className="flex items-center gap-3 mb-5">
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
                  </div>
                  <span className={`text-xs font-medium rounded-full px-2.5 py-1 capitalize ${statusColor(j.status)}`}>{j.status}</span>
                </div>

                <div className="mt-4">
                  <div className="flex items-center justify-between text-xs text-gray-600 mb-1.5">
                    <span>Hiring progress</span>
                    <span className="font-medium">{j.hired_count} / {j.openings_needed} hired</span>
                  </div>
                  <ProgressBar value={j.hired_count} max={j.openings_needed} />
                </div>

                <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100 text-sm text-gray-600">
                  <span className="flex items-center gap-1.5"><Users size={14} /> {j.candidate_count} candidates</span>
                  <span className="flex items-center gap-1.5"><Calendar size={14} /> {fmtDate(j.created_at)}</span>
                </div>

                <div className="flex gap-2 mt-4">
                  <Button variant="secondary" className="flex-1" onClick={(e) => { e.stopPropagation(); navigate(`/jobs/${j.id}`); }} data-testid={`job-view-${j.id}`}><Eye size={14} /> View</Button>
                  <Button variant="ghost" onClick={(e) => toggleStatus(e, j)} data-testid={`job-toggle-${j.id}`}>
                    {j.status === "active" ? <Pause size={14} /> : <Play size={14} />}
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <Card>
            <EmptyState icon={Briefcase} title="No jobs found" subtitle={search || statusFilter !== "all" ? "Try adjusting your filters." : "Create your first job to start hiring."} action={<Button onClick={() => navigate("/jobs/create")}><Plus size={16} /> Create Job</Button>} />
          </Card>
        )}
      </PageBody>
    </Layout>
  );
}
