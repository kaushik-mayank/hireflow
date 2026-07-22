import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Users, UserCheck, Briefcase, FileText, Sparkles, Search } from "lucide-react";
import { adminApi } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Avatar, Skeleton, EmptyState } from "@/components/ui";
import { fmtDate } from "@/constants";

const STAT_META = [
  { key: "total_users", label: "Total Users", icon: Users, color: "#4f6ef7", bg: "#e8edff" },
  { key: "active_hr", label: "Active HR (30d)", icon: UserCheck, color: "#16a34a", bg: "#dcfce7" },
  { key: "total_jobs", label: "Total Jobs", icon: Briefcase, color: "#7c3aed", bg: "#ede9fe" },
  { key: "total_resumes", label: "Total Resumes", icon: FileText, color: "#0d9488", bg: "#ccfbf1" },
  { key: "total_ai_calls", label: "Total AI Calls", icon: Sparkles, color: "#92400e", bg: "#fef3c7" },
];

export default function AdminDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    adminApi.dashboard().then((r) => setData(r.data)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const users = (data?.users || []).filter((u) =>
    `${u.name} ${u.email}`.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <Layout>
      <Topbar title="Admin Dashboard" subtitle="Platform-wide business analytics & user activity" />
      <PageBody fullWidth>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {loading
            ? STAT_META.map((s) => <Skeleton key={s.key} className="h-24 rounded-xl" />)
            : STAT_META.map((s) => (
                <Card key={s.key} className="p-4" data-testid={`admin-stat-${s.key}`}>
                  <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3" style={{ background: s.bg }}>
                    <s.icon size={18} style={{ color: s.color }} />
                  </div>
                  <div className="text-2xl font-bold text-gray-800">{data?.stats?.[s.key] ?? 0}</div>
                  <div className="text-xs text-gray-600 mt-0.5">{s.label}</div>
                </Card>
              ))}
        </div>

        <div className="grid lg:grid-cols-3 gap-6 mt-6">
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-gray-800">User Activity</h3>
              <div className="relative w-56">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search users..." className="w-full rounded-lg border border-gray-200 pl-9 pr-3 py-2 text-sm bg-white outline-none focus:border-indigo" data-testid="admin-user-search" />
              </div>
            </div>
            <Card className="overflow-hidden">
              {loading ? (
                <div className="p-4 space-y-3">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}</div>
              ) : users.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                        <th className="px-4 py-3 font-medium">User</th>
                        <th className="px-4 py-3 font-medium">Company</th>
                        <th className="px-4 py-3 font-medium">Role</th>
                        <th className="px-4 py-3 font-medium">Jobs</th>
                        <th className="px-4 py-3 font-medium">Resumes</th>
                        <th className="px-4 py-3 font-medium">AI Calls</th>
                        <th className="px-4 py-3 font-medium">Last Login</th>
                        <th className="px-4 py-3 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map((u) => (
                        <tr key={u.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50" data-testid={`admin-user-row-${u.id}`}>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <Avatar name={u.name} size={30} />
                              <div><div className="font-medium text-gray-800">{u.name}</div><div className="text-xs text-gray-400">{u.email}</div></div>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-gray-600">{u.company || "—"}</td>
                          <td className="px-4 py-3"><span className={`text-xs font-medium rounded-full px-2 py-0.5 ${u.role === "admin" ? "bg-purple-light text-purple" : "bg-indigo-light text-indigo"}`}>{u.role}</span></td>
                          <td className="px-4 py-3 text-gray-700">{u.jobs_count}</td>
                          <td className="px-4 py-3 text-gray-700">{u.resumes_count}</td>
                          <td className="px-4 py-3 text-gray-700">{u.ai_calls}</td>
                          <td className="px-4 py-3 text-gray-500 text-xs">{fmtDate(u.last_login_at)}</td>
                          <td className="px-4 py-3"><span className={`text-xs font-medium ${u.is_active ? "text-green" : "text-gray-400"}`}>{u.is_active ? "Active" : "Inactive"}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <EmptyState icon={Users} title="No users found" />}
            </Card>
          </div>

          <div>
            <h3 className="font-semibold text-gray-800 mb-3">Recent Logins</h3>
            <Card className="p-2 max-h-[460px] overflow-y-auto">
              {loading ? (
                <div className="p-3 space-y-2">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}</div>
              ) : data?.recent_logins?.length ? (
                data.recent_logins.map((lg) => (
                  <div key={lg.id} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-gray-50" data-testid={`login-${lg.id}`}>
                    <Avatar name={lg.name} size={30} color="#0d9488" />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-gray-800 truncate">{lg.name}</div>
                      <div className="text-xs text-gray-400 truncate">{lg.ip_address || "—"} · {fmtDate(lg.created_at)}</div>
                    </div>
                  </div>
                ))
              ) : <div className="p-4 text-center text-sm text-gray-400">No logins recorded</div>}
            </Card>
          </div>
        </div>
      </PageBody>
    </Layout>
  );
}
