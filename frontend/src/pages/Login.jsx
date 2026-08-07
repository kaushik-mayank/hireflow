import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Hexagon, Mail, Lock, ArrowRight, ChevronLeft, MailCheck } from "lucide-react";
import { authApi, apiErr } from "@/api";
import { useAuth } from "@/context/AuthContext";
import { Button, Spinner } from "@/components/ui";
import { pendingCompanyKey } from "@/constants";
import {
  isFirebaseConfigured, firebaseSignInRaw, firebaseCreateAccount,
  firebaseResendAndSignOut, firebaseErrorMessage, shouldTryLegacyLogin,
  firebaseSendSetupLink, firebaseIsSetupLink, firebaseStoredSetupEmail,
  firebaseCompleteSetupLink, firebaseSetPasswordForCurrentUser,
} from "@/lib/firebase";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const NOT_APPROVED_MSG =
  "You don't have an approved account yet. Contact your company's manager to be added — or, if you're starting your own organisation, use Sign up.";
const SERVER_MSG =
  "We're having trouble reaching the server right now. Please try again in a moment.";

function strength(pw) {
  let s = 0;
  if (pw.length >= 8) s++;
  if (/[A-Z]/.test(pw)) s++;
  if (/[0-9]/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  return s;
}

export default function Login() {
  // email → (onboarding-status) → verify_sent (email-link) → create (set password)
  //                              → password (existing account)
  const [step, setStep] = useState("email");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [status, setStatus] = useState(null);
  const [setupMode, setSetupMode] = useState("link"); // "link" (verify first) | "password" (fallback)
  const [linkPending, setLinkPending] = useState(false); // returned from a setup link, need the email
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  // If the page was opened from a setup email link, complete the verified sign-in
  // and move straight to choosing a password.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        if (!isFirebaseConfigured || !(await firebaseIsSetupLink())) return;
        const stored = firebaseStoredSetupEmail();
        if (!stored) {
          // Opened on a different device/browser — ask for the email to confirm.
          if (!cancelled) { setLinkPending(true); setInfo("Confirm your email to finish setting up your account."); }
          return;
        }
        setChecking(true);
        await firebaseCompleteSetupLink(stored); // now signed in with a verified email
        if (cancelled) return;
        setEmail(stored);
        setSetupMode("link");
        setStep("create");
      } catch {
        if (!cancelled) setError("That sign-in link is invalid or has expired. Please start again.");
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const backToEmail = () => {
    setStep("email"); setError(""); setInfo(""); setPassword(""); setConfirm(""); setLinkPending(false);
  };

  const legacyLogin = async () => {
    const res = await authApi.login({ email, password });
    login(res.data.token, res.data.user);
    navigate("/dashboard");
  };

  const exchangeAndFinish = async (idToken) => {
    const companyKey = pendingCompanyKey(email);
    let pendingCompany;
    try { pendingCompany = localStorage.getItem(companyKey) || undefined; } catch { /* ignore */ }
    const res = await authApi.firebase({ id_token: idToken, company: pendingCompany });
    if (!res.data.verified || !res.data.token) {
      await firebaseResendAndSignOut();
      setError("Please verify your email to continue. We've sent a new verification link to your inbox — open it, then sign in.");
      return;
    }
    try { localStorage.removeItem(companyKey); } catch { /* ignore */ }
    login(res.data.token, res.data.user);
    navigate("/dashboard");
  };

  const checkEmail = async () => {
    setError(""); setInfo("");
    if (!EMAIL_RE.test(email)) { setError("Enter a valid email address."); return; }
    setChecking(true);
    try {
      // Returning from a setup link opened elsewhere: complete it with this email.
      if (linkPending) {
        await firebaseCompleteSetupLink(email); // now signed in with a verified email
        setSetupMode("link");
        setLinkPending(false);
        setStep("create");
        return;
      }
      if (!isFirebaseConfigured) { setStatus("registered"); setStep("password"); return; }

      const { data } = await authApi.onboardingStatus(email);
      setStatus(data.status);
      if (data.status === "not_approved") { setError(NOT_APPROVED_MSG); return; }
      if (data.status === "registered") { setStep("password"); return; }

      // needs_setup → verify the email first via a secure link.
      try {
        await firebaseSendSetupLink(email);
        setSetupMode("link");
        setStep("verify_sent");
      } catch (linkErr) {
        // Email-link sign-in may not be enabled on the Firebase project. Fall
        // back to letting them set a password directly so they're never stuck.
        setSetupMode("password");
        setStep("create");
        setInfo("Choose a password to finish setting up your account.");
      }
    } catch {
      setStatus("registered");
      setStep("password");
    } finally {
      setChecking(false);
    }
  };

  const doSignIn = async () => {
    setError(""); setLoading(true);
    try {
      if (!isFirebaseConfigured) { await legacyLogin(); return; }
      let result;
      try {
        result = await firebaseSignInRaw(email, password);
      } catch (fbErr) {
        if (shouldTryLegacyLogin(fbErr)) {
          try { await legacyLogin(); return; }
          catch {
            setError(status === "not_approved" ? NOT_APPROVED_MSG : "That email or password isn't correct.");
            return;
          }
        }
        setError(firebaseErrorMessage(fbErr, "We couldn't sign you in. Please try again."));
        return;
      }
      try { await exchangeAndFinish(result.idToken); }
      catch (exErr) { setError(exErr?.response?.data?.detail || SERVER_MSG); }
    } catch (err) {
      setError(apiErr(err, "We couldn't sign you in. Please try again."));
    } finally {
      setLoading(false);
    }
  };

  const doCreate = async () => {
    setError("");
    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
    if (password !== confirm) { setError("Those passwords don't match."); return; }
    setLoading(true);
    try {
      let idToken;
      if (setupMode === "link") {
        // Email already verified via the link; just set the password.
        ({ idToken } = await firebaseSetPasswordForCurrentUser(password));
      } else {
        // Fallback: create the account with this password.
        try {
          ({ idToken } = await firebaseCreateAccount(email, password));
        } catch (createErr) {
          if (createErr?.code === "auth/email-already-in-use") {
            const r = await firebaseSignInRaw(email, password);
            idToken = r.idToken;
          } else {
            setError(firebaseErrorMessage(createErr, "We couldn't set up your account. Please try again."));
            return;
          }
        }
      }
      try { await exchangeAndFinish(idToken); }
      catch (exErr) { setError(exErr?.response?.data?.detail || SERVER_MSG); }
    } catch (err) {
      setError(firebaseErrorMessage(err, "We couldn't finish setting up your account. Please try again."));
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    if (step === "email") return checkEmail();
    if (step === "create") return doCreate();
    if (step === "verify_sent") return undefined;
    return doSignIn();
  };

  const st = strength(password);
  const stColors = ["#e5e7eb", "#ef4444", "#f59e0b", "#f59e0b", "#16a34a"];
  const inputCls =
    "w-full rounded-lg border border-gray-200 pl-9 pr-3 py-2.5 text-sm focus:border-indigo focus:ring-2 focus:ring-indigo/20 outline-none";

  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex w-[45%] bg-navy relative overflow-hidden flex-col justify-between p-12">
        <Link to="/" className="flex items-center gap-2 text-white">
          <Hexagon size={24} className="text-indigo" fill="#4f6ef7" />
          <span className="text-xl font-semibold">HireFlow</span>
        </Link>
        <div className="relative z-10">
          <h2 className="text-white text-4xl font-semibold leading-tight">From zero to hired,<br /><span className="text-indigo">powered by AI.</span></h2>
          <p className="text-white/55 mt-5 text-[15px] max-w-md leading-relaxed">
            Post a role, rank every applicant, run a visual hiring pipeline, and let AI handle the busywork — whether you're hiring nurses, warehouse staff or engineers.
          </p>
        </div>
        <div className="text-white/30 text-xs">© {new Date().getFullYear()} HireFlow</div>
        <div className="absolute -right-24 -bottom-24 w-80 h-80 rounded-full bg-indigo/20 blur-3xl" />
        <div className="absolute right-20 top-20 w-40 h-40 rounded-full bg-purple/20 blur-3xl" />
      </div>

      <div className="flex-1 flex items-center justify-center bg-gray-50 p-6">
        <div className="w-full max-w-sm animate-fade-in">
          {step === "verify_sent" ? (
            <div className="py-4" data-testid="login-verify-sent">
              <div className="w-14 h-14 rounded-2xl bg-green-light flex items-center justify-center"><MailCheck size={26} className="text-green" /></div>
              <h1 className="mt-5 text-2xl font-semibold text-gray-800">Verify your email</h1>
              <p className="text-gray-600 text-sm mt-2 leading-relaxed">
                We've sent a secure link to <span className="font-medium text-gray-800">{email}</span>. Open it on this
                device to confirm your email — then you'll choose a password.
              </p>
              <button type="button" onClick={backToEmail} className="mt-6 flex items-center gap-1.5 text-sm text-indigo hover:underline"><ChevronLeft size={15} /> Use a different email</button>
            </div>
          ) : (
            <>
              {step === "create" ? (
                <>
                  <h1 className="text-2xl font-semibold text-gray-800">Set your password</h1>
                  <p className="text-gray-600 text-sm mt-1">Your email is verified — choose a password to finish setting up <span className="font-medium text-gray-800">{email}</span>.</p>
                </>
              ) : (
                <>
                  <h1 className="text-2xl font-semibold text-gray-800">Welcome back</h1>
                  <p className="text-gray-600 text-sm mt-1">Sign in to your hiring dashboard</p>
                </>
              )}

              {error && <div className="mt-5 bg-coral-light text-coral text-sm rounded-lg px-4 py-2.5 leading-relaxed" data-testid="login-error">{error}</div>}
              {info && !error && <div className="mt-5 bg-indigo-light text-indigo text-sm rounded-lg px-4 py-2.5 leading-relaxed">{info}</div>}

              <form onSubmit={onSubmit} className="mt-6 space-y-4">
                {step === "email" ? (
                  <div>
                    <label className="text-sm font-medium text-gray-700">Email</label>
                    <div className="relative mt-1.5">
                      <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                      <input type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} placeholder="you@work-email.com" data-testid="login-email" />
                    </div>
                  </div>
                ) : (
                  <button type="button" onClick={backToEmail} className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-indigo" data-testid="login-change-email">
                    <ChevronLeft size={15} /> <span className="truncate">{email}</span>
                  </button>
                )}

                {step === "password" && (
                  <div>
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium text-gray-700">Password</label>
                      <Link to="/forgot-password" className="text-xs text-indigo font-medium hover:underline" data-testid="goto-forgot">Forgot password?</Link>
                    </div>
                    <div className="relative mt-1.5">
                      <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                      <input type="password" required autoFocus value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} placeholder="••••••••" data-testid="login-password" />
                    </div>
                  </div>
                )}

                {step === "create" && (
                  <>
                    <div>
                      <label className="text-sm font-medium text-gray-700">New password</label>
                      <div className="relative mt-1.5">
                        <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                        <input type="password" required autoFocus value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} placeholder="At least 8 characters" data-testid="login-create-password" />
                      </div>
                      {password && <div className="flex gap-1 mt-2">{[1, 2, 3, 4].map((i) => <div key={i} className="h-1 flex-1 rounded-full" style={{ background: i <= st ? stColors[st] : "#e5e7eb" }} />)}</div>}
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-700">Confirm password</label>
                      <div className="relative mt-1.5">
                        <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                        <input type="password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} className={inputCls} placeholder="••••••••" data-testid="login-confirm" />
                      </div>
                    </div>
                  </>
                )}

                <Button type="submit" disabled={loading || checking} className="w-full" data-testid="login-submit">
                  {loading || checking ? <Spinner size={16} />
                    : step === "email" ? <>Continue <ArrowRight size={16} /></>
                    : step === "create" ? <>Create account &amp; sign in <ArrowRight size={16} /></>
                    : <>Sign in <ArrowRight size={16} /></>}
                </Button>
              </form>
            </>
          )}

          <div className="mt-6 text-sm text-gray-600 text-center">
            Don't have an account?{" "}
            <Link to="/signup" className="text-indigo font-medium hover:underline" data-testid="goto-signup">Sign up</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
