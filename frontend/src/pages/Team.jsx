import { useEffect, useState, useCallback } from "react";
import { UserPlus, Users, ShieldOff, ShieldCheck, Trash2, Info, AlertCircle } from "lucide-react";
import { orgsApi, apiErr } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Avatar, Button, Modal, Skeleton, EmptyState, Pill } from "@/components/ui";
import { useAuth } from "@/context/AuthContext";
import { fmtDate } from "@/constants";
import { toast } from "sonner";

// Product copy uses "Admin" / "User"; the code uses manager / recruiter.
const ROLE_LABEL = { manager: "Admin", recruiter: "User" };
const STATUS_META = {
  active: { label: "Active", tone: "green" },
  approved: { label: "Pending sign-in", tone: "amber" },
  invited: { label: "Pending sign-in", tone: "amber" },
  disabled: { label: "Suspended", tone: "gray" },
};

function AddUserModal({ open, onClose, onDone }) {
  const [mode, setMode] = useState("single"); // "single" | "bulk"
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [bulk, setBulk] = useState("");
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null); // bulk summary { added, skipped }

  const reset = () => {
    setEmail(""); setName(""); setBulk(""); setResult(null); setSaving(false);
  };
  const close = () => { reset(); onClose(); };

  const submitSingle = async () => {
    if (!email.trim()) return;
    setSaving(true);
    try {
      await orgsApi.addMember({ email: email.trim(), name: name.trim() || undefined });
      toast.success("Teammate approved");
      onDone();
      close();
    } catch (err) {
      toast.error(apiErr(err, "Couldn't add that email."));
    } finally {
      setSaving(false);
    }
  };

  const submitBulk = async () => {
    if (!bulk.trim()) return;
    setSaving(true);
    try {
      const res = await orgsApi.addMembersBulk(bulk);
      setResult(res.data);
      const added = res.data.added?.length || 0;
      if (added) toast.success(`Approved ${added} teammate${added === 1 ? "" : "s"}`);
      else toast.message("No new emails were added — see the details below.");
      onDone();
    } catch (err) {
      toast.error(apiErr(err, "Couldn't process that list."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={close}
      title="Add teammates"
      width="max-w-lg"
      footer={
        <>
          <Button variant="secondary" onClick={close} data-testid="team-add-cancel">Close</Button>
          {mode === "single" ? (
            <Button onClick={submitSingle} disabled={saving || !email.trim()} data-testid="team-add-submit">
              {saving ? "Adding…" : "Approve email"}
            </Button>
          ) : (
            <Button onClick={submitBulk} disabled={saving || !bulk.trim()} data-testid="team-bulk-submit">
              {saving ? "Adding…" : "Approve list"}
            </Button>
          )}
        </>
      }
    >
      <div className="flex gap-1 rounded-lg bg-gray-100 p-1 mb-4 text-sm">
        <button
          className={`flex-1 rounded-md px-3 py-1.5 font-medium ${mode === "single" ? "bg-white text-gray-800 shadow-soft" : "text-gray-500"}`}
          onClick={() => { setMode("single"); setResult(null); }}
          data-testid="team-mode-single"
        >
          One at a time
        </button>
        <button
          className={`flex-1 rounded-md px-3 py-1.5 font-medium ${mode === "bulk" ? "bg-white text-gray-800 shadow-soft" : "text-gray-500"}`}
          onClick={() => { setMode("bulk"); setResult(null); }}
          data-testid="team-mode-bulk"
        >
          Paste a list
        </button>
      </div>

      <p className="text-xs text-gray-500 leading-relaxed mb-4">
        Approved teammates join as <span className="font-medium">Users</span>. They set their own password the
        first time they sign in — no invitation email is sent.
      </p>

      {mode === "single" ? (
        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium text-gray-700">Email</label>
            <input
              type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-indigo focus:ring-2 focus:ring-indigo/20"
              placeholder="teammate@company.com" data-testid="team-add-email"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-gray-700">Name <span className="text-gray-400 font-normal">(optional)</span></label>
            <input
              value={name} onChange={(e) => setName(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-indigo focus:ring-2 focus:ring-indigo/20"
              placeholder="Jordan Lee" data-testid="team-add-name"
            />
          </div>
        </div>
      ) : (
        <div>
          <label className="text-sm font-medium text-gray-700">Emails</label>
          <textarea
            value={bulk} onChange={(e) => setBulk(e.target.value)} rows={5}
            className="mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm outline-none focus:border-indigo focus:ring-2 focus:ring-indigo/20 font-mono"
            placeholder={"one@company.com, two@company.com\nthree@company.com"}
            data-testid="team-bulk-text"
          />
          <p className="text-xs text-gray-400 mt-1">Separate with commas, spaces or new lines. Paste from a spreadsheet works too.</p>
        </div>
      )}

      {result && (
        <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs" data-testid="team-bulk-result">
          <div className="font-medium text-gray-700">
            Added {result.added?.length || 0} · Skipped {result.skipped?.length || 0}
            {result.seat_limit != null && <span className="text-gray-500"> · {result.seats_used}/{result.seat_limit} seats used</span>}
          </div>
          {result.skipped?.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-gray-500">
              {result.skipped.map((s) => (
                <li key={s.email}><span className="font-mono">{s.email}</span> — {s.reason}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Modal>
  );
}

export default function Team() {
  const { user } = useAuth();
  const [org, setOrg] = useState(null);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [showAdd, setShowAdd] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const [meRes, memRes] = await Promise.all([orgsApi.me(), orgsApi.members()]);
      setOrg(meRes.data.org);
      setMembers(memRes.data);
    } catch {
      // A load failure is a server/connection problem — say that, never blame the user.
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const setStatus = async (m, status) => {
    try {
      await orgsApi.setMemberStatus(m.id, status);
      toast.success(`${m.name || m.email} ${status === "disabled" ? "suspended" : "reactivated"}`);
      load();
    } catch (err) { toast.error(apiErr(err)); }
  };

  const remove = async (m) => {
    if (!window.confirm(`Remove ${m.email}? They haven't signed in yet, so this just frees their seat.`)) return;
    try {
      await orgsApi.removeMember(m.id);
      toast.success("Member removed");
      load();
    } catch (err) { toast.error(apiErr(err)); }
  };

  const rowActions = (m) => {
    if (m.id === user?.id) return <span className="text-xs text-gray-400">You</span>;
    if (m.status === "active") {
      return (
        <Button variant="ghost" className="!px-2 !py-1.5" onClick={() => setStatus(m, "disabled")} title="Suspend" data-testid={`suspend-${m.id}`}>
          <ShieldOff size={15} className="text-coral" />
        </Button>
      );
    }
    if (m.status === "disabled") {
      return (
        <Button variant="secondary" className="!px-2 !py-1.5" onClick={() => setStatus(m, "active")} title="Reactivate" data-testid={`reactivate-${m.id}`}>
          <ShieldCheck size={15} className="text-green" />
        </Button>
      );
    }
    // approved / invited — not yet signed in; removing frees the seat.
    return (
      <Button variant="ghost" className="!px-2 !py-1.5" onClick={() => remove(m)} title="Remove" data-testid={`remove-${m.id}`}>
        <Trash2 size={15} className="text-gray-400" />
      </Button>
    );
  };

  const seatText = org ? `${org.seats_used} / ${org.seat_limit} seats` : "";

  return (
    <Layout>
      <Topbar
        title="Team"
        subtitle="Approve who can join your organisation"
        actions={
          <>
            {org && <span className="text-sm text-gray-500 mr-1" data-testid="team-seats">{seatText}</span>}
            <Button onClick={() => setShowAdd(true)} data-testid="team-add"><UserPlus size={16} /> Add user</Button>
          </>
        }
      />
      <PageBody fullWidth>
        <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-gray-200 bg-white px-4 py-3 text-xs leading-relaxed text-gray-600">
          <Info size={14} className="mt-0.5 shrink-0 text-indigo" />
          <p>
            Add teammates by approving their email — no invitation email is sent. Each person sets their own
            password the first time they sign in and joins as a <span className="font-medium">User</span>. Assign
            them to jobs from each job's page.
          </p>
        </div>

        {loadError ? (
          <Card className="p-6">
            <div className="flex items-start gap-3">
              <AlertCircle size={18} className="mt-0.5 shrink-0 text-coral" />
              <div>
                <div className="font-medium text-gray-800 text-sm">We couldn't load your team right now.</div>
                <div className="text-sm text-gray-600 mt-0.5">This looks like a connection or server problem, not anything you did.</div>
                <Button variant="secondary" className="mt-3" onClick={load} data-testid="team-retry">Try again</Button>
              </div>
            </div>
          </Card>
        ) : (
          <Card className="overflow-hidden">
            {loading ? (
              <div className="p-4 space-y-3">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-12" />)}</div>
            ) : members.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-600 text-xs border-b border-gray-200">
                      <th className="px-4 py-3 font-medium">Member</th>
                      <th className="px-4 py-3 font-medium">Role</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                      <th className="px-4 py-3 font-medium">Jobs</th>
                      <th className="px-4 py-3 font-medium">Candidates</th>
                      <th className="px-4 py-3 font-medium">Last active</th>
                      <th className="px-4 py-3 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {members.map((m) => {
                      const st = STATUS_META[m.status] || STATUS_META.approved;
                      return (
                        <tr key={m.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50" data-testid={`member-row-${m.id}`}>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <Avatar name={m.name || m.email} size={32} />
                              <div>
                                <div className="font-medium text-gray-800">{m.name || "—"}</div>
                                <div className="text-xs text-gray-400">{m.email}</div>
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`text-xs font-medium rounded-full px-2 py-0.5 ${m.org_role === "manager" ? "bg-indigo-light text-indigo" : "bg-gray-100 text-gray-600"}`}>
                              {ROLE_LABEL[m.org_role] || "User"}
                            </span>
                          </td>
                          <td className="px-4 py-3"><Pill tone={st.tone}>{st.label}</Pill></td>
                          <td className="px-4 py-3 text-gray-700">{m.jobs_assigned}</td>
                          <td className="px-4 py-3 text-gray-700">{m.candidates_sourced}</td>
                          <td className="px-4 py-3 text-gray-500 text-xs">{m.last_login_at ? fmtDate(m.last_login_at) : "—"}</td>
                          <td className="px-4 py-3"><div className="flex items-center justify-end">{rowActions(m)}</div></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                icon={Users}
                title="No teammates yet"
                subtitle="Approve a colleague's email to give them access. They'll set their own password on first sign-in."
                action={<Button onClick={() => setShowAdd(true)}><UserPlus size={16} /> Add user</Button>}
              />
            )}
          </Card>
        )}
      </PageBody>

      <AddUserModal open={showAdd} onClose={() => setShowAdd(false)} onDone={load} />
    </Layout>
  );
}
