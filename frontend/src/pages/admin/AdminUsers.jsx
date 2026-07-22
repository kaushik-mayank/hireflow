import { useEffect, useState } from "react";
import { Search, ShieldCheck, ShieldOff, UserCog } from "lucide-react";
import { adminApi, apiErr } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Avatar, Button, Skeleton, EmptyState } from "@/components/ui";
import { fmtDate } from "@/constants";
import { toast } from "sonner";

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const load = () => {
    setLoading(true);
    adminApi.users().then((r) => setUsers(r.data)).catch(() => {}).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const toggleStatus = async (u) => {
    try {
      await adminApi.setStatus(u.id, !u.is_active);
      toast.success(`${u.name} ${u.is_active ? "deactivated" : "reactivated"}`);
      load();
    } catch (err) { toast.error(apiErr(err)); }
  };

  const toggleRole = async (u) => {
    const next = u.role === "admin" ? "hr" : "admin";
    try {
      await adminApi.setRole(u.id, next);
      toast.success(`${u.name} is now ${next}`);
      load();
    } catch (err) { toast.error(apiErr(err)); }
  };

  const filtered = users.filter((u) => {
    const okSearch = `${u.name} ${u.email} ${u.company || ""}`.toLowerCase().includes(search.toLowerCase());
    const okRole = roleFilter === "all" || u.role === roleFilter;
    const okStatus = statusFilter === "all" || (statusFilter === "active" ? u.is_active : !u.is_active);
    return okSearch && okRole && okStatus;
  });

  return (
    <Layout>
      <Topbar title="User Management" subtitle="Manage accounts, roles, and access" />
      <PageBody fullWidth>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <div className="relative flex-1 min-w-[200px] max-w-sm">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name, email, company..." className="w-full rounded-lg border border-gray-200 pl-9 pr-3 py-2 text-sm bg-white outline-none focus:border-indigo" data-testid="users-search" />
          </div>
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} className="rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white" data-testid="users-role-filter">
            <option value="all">All Roles</option><option value="hr">HR</option><option value="admin">Admin</option>
          </select>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white" data-testid="users-status-filter">
            <option value="all">All Status</option><option value="active">Active</option><option value="inactive">Inactive</option>
          </select>
        </div>

        <Card className="overflow-hidden">
          {loading ? (
            <div className="p-4 space-y-3">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-12" />)}</div>
          ) : filtered.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                    <th className="px-4 py-3 font-medium">User</th>
                    <th className="px-4 py-3 font-medium">Company</th>
                    <th className="px-4 py-3 font-medium">Role</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Jobs</th>
                    <th className="px-4 py-3 font-medium">Resumes</th>
                    <th className="px-4 py-3 font-medium">AI</th>
                    <th className="px-4 py-3 font-medium">Created</th>
                    <th className="px-4 py-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((u) => (
                    <tr key={u.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50" data-testid={`user-row-${u.id}`}>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <Avatar name={u.name} size={32} />
                          <div><div className="font-medium text-gray-800">{u.name}</div><div className="text-xs text-gray-400">{u.email}</div></div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-600">{u.company || "—"}</td>
                      <td className="px-4 py-3"><span className={`text-xs font-medium rounded-full px-2 py-0.5 ${u.role === "admin" ? "bg-purple-light text-purple" : "bg-indigo-light text-indigo"}`}>{u.role}</span></td>
                      <td className="px-4 py-3"><span className={`text-xs font-medium rounded-full px-2 py-0.5 ${u.is_active ? "bg-green-light text-green" : "bg-gray-100 text-gray-400"}`}>{u.is_active ? "Active" : "Inactive"}</span></td>
                      <td className="px-4 py-3 text-gray-700">{u.jobs_count}</td>
                      <td className="px-4 py-3 text-gray-700">{u.resumes_count}</td>
                      <td className="px-4 py-3 text-gray-700">{u.ai_calls}</td>
                      <td className="px-4 py-3 text-gray-500 text-xs">{fmtDate(u.created_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button variant="ghost" className="!px-2 !py-1.5" onClick={() => toggleRole(u)} title="Change role" data-testid={`role-toggle-${u.id}`}><UserCog size={15} /></Button>
                          <Button variant={u.is_active ? "ghost" : "secondary"} className="!px-2 !py-1.5" onClick={() => toggleStatus(u)} title={u.is_active ? "Deactivate" : "Reactivate"} data-testid={`status-toggle-${u.id}`}>
                            {u.is_active ? <ShieldOff size={15} className="text-coral" /> : <ShieldCheck size={15} className="text-green" />}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <EmptyState icon={Search} title="No users match your filters" />}
        </Card>
      </PageBody>
    </Layout>
  );
}
