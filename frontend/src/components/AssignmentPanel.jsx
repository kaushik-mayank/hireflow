import { useEffect, useState, useCallback } from "react";
import { UserPlus, Trash2, Pencil } from "lucide-react";
import { assignmentsApi, orgsApi, apiErr } from "@/api";
import { Card, Button, Modal, Avatar, Pill, Skeleton, EmptyState } from "@/components/ui";
import { fmtDate } from "@/constants";
import { toast } from "sonner";

// The 8 per-assignment flags, in a sensible reading order. Labels are the
// customer-facing wording; the keys match the backend permission flags.
const PERMISSIONS = [
  ["can_upload_candidates", "Upload candidates"],
  ["can_move_stage", "Move candidates between stages"],
  ["can_reject_candidates", "Reject candidates"],
  ["can_use_ai", "Use AI tools"],
  ["can_view_team_candidates", "See the whole team's candidates"],
  ["can_edit_jd", "Edit their own copy of the JD"],
  ["can_edit_job_meta", "Edit job details"],
  ["can_close_job", "Close the job"],
];
const DEFAULT_PERMS = {
  can_upload_candidates: true, can_move_stage: true, can_reject_candidates: true,
  can_use_ai: true, can_view_team_candidates: false, can_edit_jd: false,
  can_edit_job_meta: false, can_close_job: false,
};

function AssignModal({ open, onClose, jobId, recruiters, existing, onSaved }) {
  const editing = Boolean(existing);
  const [userId, setUserId] = useState("");
  const [perms, setPerms] = useState(DEFAULT_PERMS);
  const [targets, setTargets] = useState({ shortlist_target: "", sourced_target: "", interview_target: "" });
  const [deadline, setDeadline] = useState("");
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  // Reset/prefill whenever the modal opens (new vs edit).
  useEffect(() => {
    if (!open) return;
    if (existing) {
      setUserId(existing.user_id);
      setPerms({ ...DEFAULT_PERMS, ...(existing.permissions || {}) });
      const t = existing.targets || {};
      setTargets({
        shortlist_target: t.shortlist_target ?? "",
        sourced_target: t.sourced_target ?? "",
        interview_target: t.interview_target ?? "",
      });
      setDeadline(existing.deadline ? String(existing.deadline).slice(0, 10) : "");
      setNote(existing.note || "");
    } else {
      setUserId("");
      setPerms(DEFAULT_PERMS);
      setTargets({ shortlist_target: "", sourced_target: "", interview_target: "" });
      setDeadline("");
      setNote("");
    }
  }, [open, existing]);

  const num = (v) => (v === "" || v === null || v === undefined ? null : Number(v));

  const save = async () => {
    if (!userId) { toast.error("Choose a teammate to assign"); return; }
    setSaving(true);
    try {
      await assignmentsApi.upsert(jobId, {
        user_id: userId,
        permissions: perms,
        shortlist_target: num(targets.shortlist_target),
        sourced_target: num(targets.sourced_target),
        interview_target: num(targets.interview_target),
        deadline: deadline || null,
        note: note || null,
      });
      toast.success(editing ? "Assignment updated" : "Teammate assigned");
      onSaved();
      onClose();
    } catch (err) {
      toast.error(apiErr(err, "Couldn't save the assignment."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? "Edit assignment" : "Assign a teammate"}
      width="max-w-lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={save} disabled={saving || !userId} data-testid="assign-save">
            {saving ? "Saving…" : editing ? "Save changes" : "Assign"}
          </Button>
        </>
      }
    >
      {!editing && (
        <div className="mb-4">
          <label className="text-sm font-medium text-gray-700">Teammate</label>
          <select
            value={userId} onChange={(e) => setUserId(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2.5 text-sm bg-white outline-none focus:border-indigo focus:ring-2 focus:ring-indigo/20"
            data-testid="assign-user"
          >
            <option value="" disabled>Select a teammate…</option>
            {recruiters.map((m) => <option key={m.id} value={m.id}>{(m.name || m.email)} · {m.email}</option>)}
          </select>
          {recruiters.length === 0 && (
            <p className="text-xs text-gray-400 mt-1">No teammates yet — add them from the Team page first.</p>
          )}
        </div>
      )}

      <div className="mb-1.5 text-sm font-medium text-gray-700">Permissions</div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5 mb-4">
        {PERMISSIONS.map(([key, label]) => (
          <label key={key} className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox" checked={!!perms[key]}
              onChange={(e) => setPerms((p) => ({ ...p, [key]: e.target.checked }))}
              className="accent-indigo w-4 h-4" data-testid={`perm-${key}`}
            />
            {label}
          </label>
        ))}
      </div>

      <div className="mb-1.5 text-sm font-medium text-gray-700">Targets <span className="text-gray-400 font-normal">(optional)</span></div>
      <div className="grid grid-cols-3 gap-3 mb-4">
        {[["shortlist_target", "Shortlist"], ["sourced_target", "Sourced"], ["interview_target", "Interviews"]].map(([key, label]) => (
          <div key={key}>
            <label className="text-xs text-gray-500">{label}</label>
            <input
              type="number" min="0" value={targets[key]}
              onChange={(e) => setTargets((t) => ({ ...t, [key]: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-indigo"
              data-testid={`target-${key}`}
            />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500">Deadline</label>
          <input
            type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)}
            className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-indigo"
            data-testid="assign-deadline"
          />
        </div>
        <div>
          <label className="text-xs text-gray-500">Note</label>
          <input
            value={note} onChange={(e) => setNote(e.target.value)}
            className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-indigo"
            placeholder="Optional" data-testid="assign-note"
          />
        </div>
      </div>
    </Modal>
  );
}

export default function AssignmentPanel({ jobId }) {
  const [assignments, setAssignments] = useState([]);
  const [recruiters, setRecruiters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([assignmentsApi.listForJob(jobId), orgsApi.members()])
      .then(([a, m]) => {
        setAssignments(a.data);
        setRecruiters((m.data || []).filter((x) => x.org_role === "recruiter" && x.status !== "disabled"));
      })
      .catch(() => toast.error("Could not load assignments"))
      .finally(() => setLoading(false));
  }, [jobId]);
  useEffect(load, [load]);

  const revoke = async (a) => {
    if (!window.confirm(`Remove ${a.user_name || a.user_email} from this job? Candidates they added stay on the job.`)) return;
    try {
      await assignmentsApi.revoke(jobId, a.user_id);
      toast.success("Assignment removed");
      load();
    } catch (err) { toast.error(apiErr(err)); }
  };

  const openNew = () => { setEditing(null); setModalOpen(true); };
  const openEdit = (a) => { setEditing(a); setModalOpen(true); };
  const grantedCount = (perms) => Object.values(perms || {}).filter(Boolean).length;

  return (
    <Card className="p-0 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
        <div>
          <h3 className="font-semibold text-gray-800">Assigned recruiters</h3>
          <p className="text-xs text-gray-500 mt-0.5">Give teammates access to this job with their own permissions, targets and deadline.</p>
        </div>
        <Button onClick={openNew} data-testid="assign-add"><UserPlus size={16} /> Assign teammate</Button>
      </div>

      {loading ? (
        <div className="p-4 space-y-3">{[1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div>
      ) : assignments.length ? (
        <div className="divide-y divide-gray-100">
          {assignments.map((a) => (
            <div key={a.id} className="flex items-center gap-3 px-5 py-3.5" data-testid={`assignment-${a.user_id}`}>
              <Avatar name={a.user_name || a.user_email} size={36} />
              <div className="min-w-0 flex-1">
                <div className="font-medium text-gray-800 text-sm">{a.user_name || "—"}</div>
                <div className="text-xs text-gray-400">{a.user_email}</div>
                <div className="flex flex-wrap items-center gap-1.5 mt-1">
                  <Pill tone="gray">{grantedCount(a.permissions)} permissions</Pill>
                  {a.deadline && <Pill tone="amber">Due {fmtDate(a.deadline)}</Pill>}
                  {a.targets?.shortlist_target != null && <Pill tone="gray">Shortlist {a.targets.shortlist_target}</Pill>}
                </div>
              </div>
              <button onClick={() => openEdit(a)} className="p-2 text-gray-500 hover:text-indigo hover:bg-indigo-light rounded-lg" title="Edit" data-testid={`assignment-edit-${a.user_id}`}><Pencil size={15} /></button>
              <button onClick={() => revoke(a)} className="p-2 text-gray-500 hover:text-coral hover:bg-coral-light rounded-lg" title="Remove" data-testid={`assignment-remove-${a.user_id}`}><Trash2 size={15} /></button>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={UserPlus}
          title="No one assigned yet"
          subtitle="Assign a teammate to let them work this job with their own permissions."
          action={<Button onClick={openNew}><UserPlus size={16} /> Assign teammate</Button>}
        />
      )}

      <AssignModal
        open={modalOpen} onClose={() => setModalOpen(false)} jobId={jobId}
        recruiters={recruiters} existing={editing} onSaved={load}
      />
    </Card>
  );
}
