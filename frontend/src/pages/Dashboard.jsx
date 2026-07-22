import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Briefcase, CheckCircle2, Users, Clock, Gauge, Plus, AlertTriangle, CalendarClock, Sparkles } from "lucide-react";
import { dashboardApi, aiApi, apiErr } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Button, AIButton, StageBadge, ProgressBar, Avatar, Skeleton, EmptyState } from "@/components/ui";
import { fmtDate } from "@/constants";
import { toast } from "sonner";

const STAT_META = [
  { key: "active_jobs", label: "Active Jobs", icon: Briefcase, color: "#4f6ef7", bg: "#e8edff" },
  { key: "total_hired", label: "Total Hired", icon: CheckCircle2, color: "#16a34a", bg: "#dcfce7" },
  { key: "in_pipeline", label: "In Pipeline", icon: Users, color: "#7c3aed", bg: "#ede9fe" },
  { key: "contact_pending", label: "Contact Pending", icon: Clock, color: "#92400e", bg: "#fef3c7" },
  { key: "avg_score", label: "Avg Match Score", icon: Gauge, color: "#0d9488", bg: "#ccfbf1" },
];

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState("");
  const [healthLoading, setHealthLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    dashboardApi.get().then((r) => setData(r.data)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const getHealth = async () => {
    setHealthLoading(true);
    try {
      const r = await aiApi.pipelineHealth();
      setHealth(r.data.report);
    } catch (err) {
      toast.error(apiErr(err, "Could not generate health report"));
    } finally {
      setHealthLoading(false);
    }
  };

  return (
    <Layout>
      <Topbar
        title="Dashboard"
        subtitle="Your hiring command center"
        actions={<Button onClick={() => navigate("/jobs/create")} data-testid="dash-create-job"><Plus size={16} /> Create Job</Button>}
      />
      <PageBody>
        {/* Stat cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {loading
            ? STAT_META.map((s) => <Skeleton key={s.key} className="h-24 rounded-xl" />)
            : STAT_META.map((s) => {
                const val = data?.stats?.[s.key] ?? 0;
                const highlight = s.key === "contact_pending" && val > 0;
                return (
                  <Card key={s.key} className={`p-4 ${highlight ? "ring-1 ring-amber/40" : ""}`} data-testid={`stat-${s.key}`}>
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3" style={{ background: s.bg }}>
                      <s.icon size={18} style={{ color: s.color }} />
                    </div>
                    <div className="text-2xl font-bold text-gray-800">{val}</div>
                    <div className="text-xs text-gray-600 mt-0.5">{s.label}</div>
                  </Card>
                );
              })}
        </div>

        {/* AI Pipeline Health */}
        <Card className="mt-6 p-5" data-testid="health-widget">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles size={18} className="text-amber" />
              <h3 className="font-semibold text-gray-800">AI Pipeline Health</h3>
            </div>
            <AIButton loading={healthLoading} onClick={getHealth} data-testid="get-health-btn">
              {healthLoading ? "Analyzing..." : "Get AI Health Report"}
            </AIButton>
          </div>
          {health ? (
            <p className="mt-4 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap" data-testid="health-result">{health}</p>
          ) : (
            <p className="mt-3 text-sm text-gray-400">Get an AI-generated assessment of your hiring pipeline, bottlenecks, and next actions.</p>
          )}
        </Card>

        <div className="grid lg:grid-cols-3 gap-6 mt-6">
          {/* Jobs summary table */}
          <div className="lg:col-span-2">
            <h3 className="font-semibold text-gray-800 mb-3">Jobs Overview</h3>
            <Card className="overflow-hidden">
              {loading ? (
                <div className="p-4 space-y-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}</div>
              ) : data?.jobs_summary?.length ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                      <th className="px-4 py-3 font-medium">Job</th>
                      <th className="px-4 py-3 font-medium">Progress</th>
                      <th className="px-4 py-3 font-medium">Candidates</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.jobs_summary.map((j) => (
                      <tr key={j.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50 cursor-pointer" onClick={() => navigate(`/jobs/${j.id}`)} data-testid={`dash-job-${j.id}`}>
                        <td className="px-4 py-3">
                          <div className="font-medium text-gray-800">{j.title}</div>
                          <div className="text-xs text-gray-400">{j.department || "—"} · {fmtDate(j.created_at)}</div>
                        </td>
                        <td className="px-4 py-3 w-40">
                          <div className="flex items-center gap-2">
                            <ProgressBar value={j.hired} max={j.openings_needed} />
                            <span className="text-xs text-gray-600 whitespace-nowrap">{j.hired}/{j.openings_needed}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-700">{j.candidate_count}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-medium capitalize ${j.status === "active" ? "text-green" : "text-gray-400"}`}>{j.status}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <EmptyState icon={Briefcase} title="No jobs yet" subtitle="Create your first job to start hiring." action={<Button onClick={() => navigate("/jobs/create")}><Plus size={16} /> Create Job</Button>} />
              )}
            </Card>
          </div>

          {/* Right column: action items + interviews */}
          <div className="space-y-6">
            <div>
              <h3 className="font-semibold text-gray-800 mb-3">Action Items</h3>
              <Card className="p-2">
                {loading ? (
                  <div className="p-3 space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-8" />)}</div>
                ) : data?.action_items?.length ? (
                  data.action_items.map((a, i) => (
                    <div key={i} className="flex items-start gap-2.5 p-2.5 rounded-lg hover:bg-amber-light/40 cursor-pointer" onClick={() => navigate("/jobs")} data-testid={`action-${a.type}`}>
                      <AlertTriangle size={15} className="text-amber mt-0.5 shrink-0" />
                      <span className="text-sm text-gray-700">{a.text}</span>
                    </div>
                  ))
                ) : (
                  <div className="p-4 text-center text-sm text-gray-400">All caught up! No pending actions.</div>
                )}
              </Card>
            </div>

            <div>
              <h3 className="font-semibold text-gray-800 mb-3">Upcoming Interviews</h3>
              <Card className="p-2">
                {loading ? (
                  <div className="p-3 space-y-2">{[1, 2].map((i) => <Skeleton key={i} className="h-10" />)}</div>
                ) : data?.upcoming_interviews?.length ? (
                  data.upcoming_interviews.map((c) => (
                    <div key={c.id} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-gray-50 cursor-pointer" onClick={() => navigate(`/candidates/${c.id}`)} data-testid={`interview-${c.id}`}>
                      <Avatar name={c.name} size={32} color="#7c3aed" />
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-gray-800 truncate">{c.name}</div>
                        <div className="text-xs text-gray-400 truncate">{c.job_title}</div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="p-4 text-center text-sm text-gray-400 flex flex-col items-center gap-2">
                    <CalendarClock size={20} className="text-gray-300" />
                    No interviews scheduled
                  </div>
                )}
              </Card>
            </div>
          </div>
        </div>
      </PageBody>
    </Layout>
  );
}
