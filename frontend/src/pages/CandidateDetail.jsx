import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Mail, Phone, ChevronDown, ChevronUp, Sparkles, FileText, GitCompare, MessageSquareText, Send, XCircle } from "lucide-react";
import { candidatesApi, aiApi, apiErr } from "@/api";
import Layout, { Topbar, PageBody } from "@/components/Layout";
import { Card, Button, AIButton, ScoreBadge, StageBadge, Avatar, Pill, Modal, Spinner, Skeleton } from "@/components/ui";
import { STAGES, fmtDate } from "@/constants";
import { toast } from "sonner";

export default function CandidateDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [cand, setCand] = useState(null);
  const [loading, setLoading] = useState(true);
  const [resumeOpen, setResumeOpen] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [siblings, setSiblings] = useState([]);

  // AI states
  const [questions, setQuestions] = useState(null);
  const [summary, setSummary] = useState(null);
  const [email, setEmail] = useState(null);
  const [compare, setCompare] = useState(null);
  const [loadingAction, setLoadingAction] = useState("");
  const [compareModal, setCompareModal] = useState(false);

  const load = () => {
    candidatesApi.get(id).then((r) => {
      setCand(r.data);
      candidatesApi.listByJob(r.data.job_id).then((s) => setSiblings(s.data.filter((c) => c.id !== id)));
    }).catch(() => toast.error("Could not load candidate")).finally(() => setLoading(false));
  };
  useEffect(load, [id]);

  const moveStage = async (stage) => {
    try {
      const r = await candidatesApi.updateStage(id, { stage });
      if (r.data.quota_met) toast.success("🎉 Hiring quota met!");
      else toast.success(`Moved to ${stage}`);
      load();
    } catch (err) { toast.error(apiErr(err)); }
  };

  const addNote = async () => {
    if (!noteText.trim()) return;
    try { await candidatesApi.addNote(id, noteText); setNoteText(""); toast.success("Note saved"); load(); }
    catch (err) { toast.error(apiErr(err)); }
  };

  const run = async (action, fn, setter) => {
    setLoadingAction(action);
    try { const r = await fn(); setter(r.data); }
    catch (err) { toast.error(apiErr(err, "AI action failed")); }
    finally { setLoadingAction(""); }
  };

  const doCompare = async (otherId) => {
    setCompareModal(false);
    setLoadingAction("compare");
    try { const r = await aiApi.compare(id, otherId); setCompare(r.data); }
    catch (err) { toast.error(apiErr(err)); }
    finally { setLoadingAction(""); }
  };

  if (loading) return <Layout><Topbar title="Loading..." /><PageBody><Skeleton className="h-96 rounded-xl" /></PageBody></Layout>;
  if (!cand) return null;

  return (
    <Layout>
      <Topbar title="Candidate Profile" actions={<Button variant="ghost" onClick={() => navigate(`/jobs/${cand.job_id}`)}><ArrowLeft size={16} /> Back to Job</Button>} />
      <PageBody>
        <div className="grid lg:grid-cols-5 gap-6">
          {/* Left 60% */}
          <div className="lg:col-span-3 space-y-5">
            <Card className="p-6">
              <div className="flex items-start gap-4">
                <Avatar name={cand.name} size={56} />
                <div className="flex-1">
                  <h2 className="text-xl font-semibold text-gray-800">{cand.name}</h2>
                  <div className="flex flex-wrap gap-3 mt-1.5 text-sm text-gray-600">
                    {cand.email && <span className="flex items-center gap-1"><Mail size={14} /> {cand.email}</span>}
                    {cand.phone && <span className="flex items-center gap-1"><Phone size={14} /> {cand.phone}</span>}
                  </div>
                  <button onClick={() => navigate(`/jobs/${cand.job_id}`)} className="text-sm text-indigo hover:underline mt-2">{cand.job?.title}</button>
                </div>
              </div>

              <div className="flex items-center gap-6 mt-6 pt-6 border-t border-gray-100">
                <div>
                  <ScoreBadge score={cand.ai_score} large />
                  <div className="text-xs text-gray-500 mt-1">AI Match Score</div>
                </div>
                {cand.ai_summary && <p className="text-sm text-gray-700 leading-relaxed flex-1">{cand.ai_summary}</p>}
              </div>

              {!cand.analyzed_at && (
                <div className="mt-4 bg-amber-light/50 rounded-lg px-4 py-2.5 text-sm text-[#92400e]">This candidate hasn't been analyzed by AI yet. Run "Analyze All Candidates" on the job page.</div>
              )}

              {cand.matched_skills?.length > 0 && (
                <div className="mt-5">
                  <div className="text-xs font-semibold text-gray-600 uppercase mb-2">Matched Skills</div>
                  <div className="flex flex-wrap gap-1.5">{cand.matched_skills.map((s) => <Pill key={s} tone="green">{s}</Pill>)}</div>
                </div>
              )}
              {cand.missing_skills?.length > 0 && (
                <div className="mt-4">
                  <div className="text-xs font-semibold text-gray-600 uppercase mb-2">Missing Skills</div>
                  <div className="flex flex-wrap gap-1.5">{cand.missing_skills.map((s) => <Pill key={s} tone="red">{s}</Pill>)}</div>
                </div>
              )}
              {cand.red_flags?.length > 0 && (
                <div className="mt-4">
                  <div className="text-xs font-semibold text-gray-600 uppercase mb-2">Red Flags</div>
                  <div className="flex flex-wrap gap-1.5">{cand.red_flags.map((s) => <Pill key={s} tone="amber">{s}</Pill>)}</div>
                </div>
              )}
            </Card>

            {/* Resume preview */}
            <Card className="p-5">
              <button onClick={() => setResumeOpen(!resumeOpen)} className="flex items-center justify-between w-full" data-testid="resume-toggle">
                <span className="font-semibold text-gray-800 flex items-center gap-2"><FileText size={16} /> Resume {cand.pdf_original_name && <span className="text-xs text-gray-400 font-normal">({cand.pdf_original_name})</span>}</span>
                {resumeOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
              </button>
              {resumeOpen && <pre className="mt-4 whitespace-pre-wrap font-mono text-xs text-gray-600 leading-relaxed max-h-96 overflow-y-auto bg-gray-50 rounded-lg p-4">{cand.resume_text}</pre>}
            </Card>

            {/* AI result panels */}
            {summary && <AIPanel title="Deep Candidate Summary" onClose={() => setSummary(null)}>
              <p className="text-sm font-medium text-gray-800">{summary.overall_fit}</p>
              <div className="mt-2"><span className="text-xs font-semibold text-gray-500 uppercase">Recommendation: </span><Pill tone={summary.recommendation?.includes("Yes") ? "green" : summary.recommendation === "No" ? "red" : "amber"}>{summary.recommendation}</Pill></div>
              <SkillList label="Strengths" items={summary.strengths} tone="green" />
              <SkillList label="Concerns" items={summary.concerns} tone="red" />
              <SkillList label="Experience Highlights" items={summary.experience_highlights} tone="gray" />
            </AIPanel>}

            {questions && <AIPanel title="Screening Questions" onClose={() => setQuestions(null)}>
              <div className="space-y-2">{questions.map((q, i) => (
                <div key={i} className="bg-gray-50 rounded-lg p-3"><Pill tone="amber">{q.type}</Pill><p className="text-sm text-gray-700 mt-1.5">{q.question}</p></div>
              ))}</div>
            </AIPanel>}

            {compare && <AIPanel title={`Compare: ${compare.candidate_a_name} vs ${compare.candidate_b_name}`} onClose={() => setCompare(null)}>
              <div className="bg-indigo-light/50 rounded-lg p-3 mb-3"><span className="text-xs font-semibold text-indigo uppercase">Recommended: </span><span className="font-medium text-gray-800">{compare.recommendation}</span><p className="text-sm text-gray-700 mt-1">{compare.reasoning}</p></div>
              <div className="grid grid-cols-2 gap-3">
                <SkillList label={compare.candidate_a_name} items={compare.candidate_a_strengths} tone="gray" />
                <SkillList label={compare.candidate_b_name} items={compare.candidate_b_strengths} tone="gray" />
              </div>
            </AIPanel>}
          </div>

          {/* Right 40% */}
          <div className="lg:col-span-2 space-y-5">
            <Card className="p-5">
              <div className="text-xs font-semibold text-gray-600 uppercase mb-2">Current Stage</div>
              <StageBadge stage={cand.stage} className="!text-sm !px-3 !py-1" />
              <div className="grid grid-cols-2 gap-2 mt-4">
                <Button variant="secondary" onClick={() => moveStage("Selected")} className="!text-xs" data-testid="action-select"><Send size={14} /> Select</Button>
                <Button variant="secondary" onClick={() => moveStage("Rejected")} className="!text-xs" data-testid="action-reject"><XCircle size={14} /> Reject</Button>
                <Button variant="secondary" onClick={() => moveStage("Interview Scheduled")} className="!text-xs">Schedule</Button>
                <Button variant="secondary" onClick={() => moveStage("On Hold")} className="!text-xs">On Hold</Button>
              </div>
              <select onChange={(e) => e.target.value && moveStage(e.target.value)} value="" className="w-full mt-2 rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white" data-testid="stage-select">
                <option value="" disabled>Move to other stage...</option>
                {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </Card>

            <Card className="p-5">
              <div className="flex items-center gap-2 mb-3"><Sparkles size={16} className="text-amber" /><h3 className="font-semibold text-gray-800">AI Actions</h3></div>
              <div className="space-y-2">
                <AIButton loading={loadingAction === "questions"} onClick={() => run("questions", () => aiApi.questions(id), (d) => setQuestions(d.questions))} className="w-full justify-start" data-testid="ai-questions"><MessageSquareText size={15} /> Generate Screening Questions</AIButton>
                <AIButton loading={loadingAction === "invite"} onClick={() => run("invite", () => aiApi.email(id, "interview invite"), setEmail)} className="w-full justify-start" data-testid="ai-invite"><Send size={15} /> Draft Interview Invite</AIButton>
                <AIButton loading={loadingAction === "reject"} onClick={() => run("reject", () => aiApi.email(id, "rejection"), setEmail)} className="w-full justify-start" data-testid="ai-reject-email"><XCircle size={15} /> Draft Rejection Email</AIButton>
                <AIButton loading={loadingAction === "summary"} onClick={() => run("summary", () => aiApi.summary(id), setSummary)} className="w-full justify-start" data-testid="ai-summary"><FileText size={15} /> Deep Candidate Summary</AIButton>
                <AIButton loading={loadingAction === "compare"} onClick={() => setCompareModal(true)} disabled={siblings.length === 0} className="w-full justify-start" data-testid="ai-compare"><GitCompare size={15} /> Compare with Another</AIButton>
              </div>
            </Card>

            <Card className="p-5">
              <h3 className="font-semibold text-gray-800 mb-3">Notes</h3>
              <textarea value={noteText} onChange={(e) => setNoteText(e.target.value)} rows={3} placeholder="Add a note..." className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo" data-testid="note-input" />
              <Button onClick={addNote} className="mt-2 w-full" disabled={!noteText.trim()} data-testid="note-save">Save Note</Button>
              <div className="mt-4 space-y-2">
                {(cand.notes || []).slice().reverse().map((n) => (
                  <div key={n.id} className="bg-gray-50 rounded-lg p-3 text-sm">
                    <p className="text-gray-700">{n.text}</p>
                    <p className="text-xs text-gray-400 mt-1">{n.author} · {fmtDate(n.created_at)}</p>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-5">
              <h3 className="font-semibold text-gray-800 mb-3">Activity Timeline</h3>
              {cand.transitions?.length ? (
                <div className="space-y-3">
                  {cand.transitions.map((t) => (
                    <div key={t.id} className="flex gap-3 text-sm">
                      <div className="w-2 h-2 rounded-full bg-indigo mt-1.5 shrink-0" />
                      <div><span className="text-gray-700">{t.from_stage ? `${t.from_stage} → ` : ""}<span className="font-medium">{t.to_stage}</span></span><div className="text-xs text-gray-400">{t.moved_by} · {fmtDate(t.moved_at)}</div></div>
                    </div>
                  ))}
                </div>
              ) : <p className="text-sm text-gray-400">No stage changes yet.</p>}
            </Card>
          </div>
        </div>
      </PageBody>

      {/* Email modal */}
      {email && (
        <Modal open onClose={() => setEmail(null)} title="Draft Email" width="max-w-xl"
          footer={<Button onClick={() => { navigator.clipboard.writeText(`Subject: ${email.subject}\n\n${email.body}`); toast.success("Copied to clipboard"); }} data-testid="email-copy">Copy to Clipboard</Button>}>
          <label className="text-xs font-semibold text-gray-500 uppercase">Subject</label>
          <input defaultValue={email.subject} className="w-full font-medium border border-gray-200 rounded-lg px-3 py-2 text-sm mb-3 mt-1" data-testid="email-subject" />
          <label className="text-xs font-semibold text-gray-500 uppercase">Body</label>
          <textarea defaultValue={email.body} rows={12} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm leading-relaxed mt-1" data-testid="email-body" />
        </Modal>
      )}

      {/* Compare modal */}
      <Modal open={compareModal} onClose={() => setCompareModal(false)} title="Compare with another candidate" width="max-w-md">
        <p className="text-sm text-gray-600 mb-3">Select a candidate from the same job to compare:</p>
        <div className="space-y-2 max-h-72 overflow-y-auto">
          {siblings.map((s) => (
            <button key={s.id} onClick={() => doCompare(s.id)} className="w-full flex items-center gap-3 p-2.5 rounded-lg border border-gray-200 hover:bg-gray-50 text-left" data-testid={`compare-pick-${s.id}`}>
              <Avatar name={s.name} size={32} /><span className="text-sm font-medium text-gray-800 flex-1">{s.name}</span><ScoreBadge score={s.ai_score} />
            </button>
          ))}
        </div>
      </Modal>
    </Layout>
  );
}

function AIPanel({ title, onClose, children }) {
  return (
    <Card className="p-5 border-amber/30 animate-fade-in">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-800 flex items-center gap-2"><Sparkles size={15} className="text-amber" /> {title}</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-700"><XCircle size={16} /></button>
      </div>
      {children}
    </Card>
  );
}

function SkillList({ label, items, tone }) {
  if (!items?.length) return null;
  return (
    <div className="mt-3">
      <div className="text-xs font-semibold text-gray-500 uppercase mb-1.5">{label}</div>
      <ul className="space-y-1">{items.map((it, i) => <li key={i} className="text-sm text-gray-700 flex gap-2"><span className="text-gray-300">•</span> {it}</li>)}</ul>
    </div>
  );
}
