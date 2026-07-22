import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Zap, X, ExternalLink, Sparkles } from "lucide-react";
import { jobsApi, candidatesApi, aiApi, apiErr } from "@/api";
import { Sidebar, Topbar } from "@/components/Layout";
import { ScoreBadge, StageBadge, Avatar, Pill, AIButton, Button, Spinner, Modal } from "@/components/ui";
import { STAGES, STAGE_COLORS } from "@/constants";
import { toast } from "sonner";

export default function CandidateBoard() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [cands, setCands] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dragId, setDragId] = useState(null);
  const [dragOverStage, setDragOverStage] = useState(null);
  const [panel, setPanel] = useState(null);

  const load = useCallback(() => {
    Promise.all([jobsApi.get(id), candidatesApi.listByJob(id)])
      .then(([j, c]) => { setJob(j.data); setCands(c.data); })
      .catch(() => toast.error("Could not load board"))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(load, [load]);

  const onDrop = async (stage) => {
    setDragOverStage(null);
    const cand = cands.find((c) => c.id === dragId);
    setDragId(null);
    if (!cand || cand.stage === stage) return;
    const prev = cand.stage;
    setCands((cs) => cs.map((c) => (c.id === cand.id ? { ...c, stage } : c)));
    try {
      const r = await candidatesApi.updateStage(cand.id, { stage });
      if (r.data.quota_met) toast.success(`🎉 Hiring quota met for ${job.title}!`);
      else toast.success(`${cand.name} → ${stage}`);
    } catch (err) {
      setCands((cs) => cs.map((c) => (c.id === cand.id ? { ...c, stage: prev } : c)));
      toast.error(apiErr(err, "Could not move candidate"));
    }
  };

  if (loading) return (
    <div className="min-h-screen bg-gray-50"><Sidebar /><main className="ml-60"><Topbar title="Loading board..." /><div className="p-6"><Spinner className="text-indigo" /></div></main></div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />
      <main className="ml-60 h-screen flex flex-col">
        <Topbar
          title={`${job.title} · Pipeline`}
          subtitle={`${cands.length} candidates · ${job.hired_count}/${job.openings_needed} hired`}
          actions={<Button variant="ghost" onClick={() => navigate(`/jobs/${id}`)}><ArrowLeft size={16} /> Back to Job</Button>}
        />
        <div className="flex-1 overflow-x-auto kanban-scroll p-5">
          <div className="flex gap-3 h-full min-w-max">
            {STAGES.map((stage) => {
              const items = cands.filter((c) => c.stage === stage);
              const sc = STAGE_COLORS[stage];
              const isOver = dragOverStage === stage;
              return (
                <div
                  key={stage}
                  className={`w-72 shrink-0 flex flex-col rounded-xl transition-colors ${isOver ? "bg-indigo-light/60" : "bg-gray-100/70"}`}
                  onDragOver={(e) => { e.preventDefault(); setDragOverStage(stage); }}
                  onDragLeave={() => setDragOverStage((s) => (s === stage ? null : s))}
                  onDrop={() => onDrop(stage)}
                  data-testid={`kanban-col-${stage}`}
                >
                  <div className="flex items-center justify-between px-3 py-3 sticky top-0">
                    <span className="text-xs font-semibold rounded-full px-2.5 py-1" style={{ background: sc.bg, color: sc.color }}>{stage}</span>
                    <span className="text-xs text-gray-500 font-medium">{items.length}</span>
                  </div>
                  <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-2 min-h-[120px]">
                    {items.length === 0 && (
                      <div className="border-2 border-dashed border-gray-200 rounded-lg py-6 text-center text-xs text-gray-400">Drop here</div>
                    )}
                    {items.map((c) => (
                      <div
                        key={c.id}
                        draggable
                        onDragStart={() => setDragId(c.id)}
                        onDragEnd={() => { setDragId(null); setDragOverStage(null); }}
                        onClick={() => setPanel(c)}
                        className={`bg-white rounded-lg border border-gray-200 p-3 cursor-grab active:cursor-grabbing hover:shadow-card transition-all ${dragId === c.id ? "opacity-40" : ""}`}
                        data-testid={`kanban-card-${c.id}`}
                      >
                        <div className="flex items-center gap-2">
                          <Avatar name={c.name} size={28} />
                          <span className="text-sm font-medium text-gray-800 truncate flex-1">{c.name}</span>
                          <ScoreBadge score={c.ai_score} />
                        </div>
                        <div className="flex flex-wrap gap-1 mt-2">
                          {(c.matched_skills || []).slice(0, 2).map((s) => <Pill key={s} tone="green">{s}</Pill>)}
                        </div>
                        {c.stage === "Contact Pending" && (
                          <div className="flex items-center gap-1 mt-2 text-[11px] font-medium text-amber"><Zap size={11} /> Needs action</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </main>

      {panel && <CandidatePanel candidate={panel} job={job} onClose={() => setPanel(null)} onUpdated={load} navigate={navigate} />}
    </div>
  );
}

function CandidatePanel({ candidate, job, onClose, onUpdated, navigate }) {
  const [moving, setMoving] = useState(false);
  const [qLoading, setQLoading] = useState(false);
  const [emailLoading, setEmailLoading] = useState(false);
  const [questions, setQuestions] = useState(null);
  const [email, setEmail] = useState(null);

  const move = async (stage) => {
    setMoving(true);
    try {
      const r = await candidatesApi.updateStage(candidate.id, { stage });
      if (r.data.quota_met) toast.success(`🎉 Quota met for ${job.title}!`);
      else toast.success(`Moved to ${stage}`);
      onUpdated();
      onClose();
    } catch (err) { toast.error(apiErr(err)); } finally { setMoving(false); }
  };

  const genQuestions = async () => {
    setQLoading(true);
    try { const r = await aiApi.questions(candidate.id); setQuestions(r.data.questions); }
    catch (err) { toast.error(apiErr(err)); } finally { setQLoading(false); }
  };

  const draftEmail = async () => {
    setEmailLoading(true);
    try { const r = await aiApi.email(candidate.id, "interview invite"); setEmail(r.data); }
    catch (err) { toast.error(apiErr(err)); } finally { setEmailLoading(false); }
  };

  return (
    <>
      <div className="fixed inset-0 z-40 bg-navy/20" onClick={onClose} />
      <div className="fixed right-0 top-0 bottom-0 w-[400px] bg-white z-50 shadow-lift flex flex-col animate-slide-in" data-testid="kanban-panel">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <Avatar name={candidate.name} size={40} />
            <div>
              <div className="font-semibold text-gray-800">{candidate.name}</div>
              <StageBadge stage={candidate.stage} />
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 p-1"><X size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          <div className="flex items-center gap-4">
            <ScoreBadge score={candidate.ai_score} large />
            <div className="text-xs text-gray-500">AI Match Score</div>
          </div>
          {candidate.ai_summary && <p className="text-sm text-gray-700 leading-relaxed">{candidate.ai_summary}</p>}

          {(candidate.matched_skills?.length > 0) && (
            <div>
              <div className="text-xs font-semibold text-gray-600 uppercase mb-2">Matched Skills</div>
              <div className="flex flex-wrap gap-1.5">{candidate.matched_skills.map((s) => <Pill key={s} tone="green">{s}</Pill>)}</div>
            </div>
          )}
          {(candidate.missing_skills?.length > 0) && (
            <div>
              <div className="text-xs font-semibold text-gray-600 uppercase mb-2">Missing Skills</div>
              <div className="flex flex-wrap gap-1.5">{candidate.missing_skills.map((s) => <Pill key={s} tone="red">{s}</Pill>)}</div>
            </div>
          )}

          <div>
            <div className="text-xs font-semibold text-gray-600 uppercase mb-2">Move to Stage</div>
            <div className="grid grid-cols-2 gap-2">
              {["Shortlisted", "Interview Scheduled", "Selected", "Rejected"].map((s) => (
                <Button key={s} variant="secondary" disabled={moving} onClick={() => move(s)} className="!text-xs !py-1.5" data-testid={`panel-move-${s}`}>{s}</Button>
              ))}
            </div>
          </div>

          <div className="space-y-2 pt-2 border-t border-gray-100">
            <AIButton loading={qLoading} onClick={genQuestions} className="w-full" data-testid="panel-questions">Generate Questions</AIButton>
            <AIButton loading={emailLoading} onClick={draftEmail} className="w-full" data-testid="panel-email">Draft Email</AIButton>
            <Button variant="ghost" onClick={() => navigate(`/candidates/${candidate.id}`)} className="w-full" data-testid="panel-full-profile"><ExternalLink size={15} /> Full Profile</Button>
          </div>

          {questions && (
            <div className="space-y-2">
              <div className="text-xs font-semibold text-amber uppercase flex items-center gap-1"><Sparkles size={12} /> Screening Questions</div>
              {questions.map((q, i) => (
                <div key={i} className="bg-gray-50 rounded-lg p-3">
                  <Pill tone="amber">{q.type}</Pill>
                  <p className="text-sm text-gray-700 mt-1.5">{q.question}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {email && (
        <Modal open onClose={() => setEmail(null)} title="Draft Email" width="max-w-xl"
          footer={<Button onClick={() => { navigator.clipboard.writeText(`Subject: ${email.subject}\n\n${email.body}`); toast.success("Copied"); }}>Copy</Button>}>
          <input defaultValue={email.subject} className="w-full font-medium border border-gray-200 rounded-lg px-3 py-2 text-sm mb-3" />
          <textarea defaultValue={email.body} rows={12} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm leading-relaxed" />
        </Modal>
      )}
    </>
  );
}
