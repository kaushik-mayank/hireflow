import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Hexagon, Mail, Lock, ArrowRight, ChevronLeft } from "lucide-react";
import { authApi, apiErr } from "@/api";
import { useAuth } from "@/context/AuthContext";
import { Button, Spinner } from "@/components/ui";
import { pendingCompanyKey } from "@/constants";
import {
  isFirebaseConfigured, firebaseSignInRaw, firebaseCreateAccount,
  firebaseResendAndSignOut, firebaseErrorMessage, shouldTryLegacyLogin,
} from "@/lib/firebase";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const NOT_APPROVED_MSG =
  "We couldn't find an account for this email. If an admin added you to a team, double-check it's spelled the same way — otherwise ask them to add you. Starting your own organisation? Use Sign up.";
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
  // Email-first flow: enter the email, then either set a first-time password
  // (admin-approved teammate), sign in normally, or see a clear message.
  const [step, setStep] = useState("email"); // "email" | "password" | "create"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [status, setStatus] = useState(null); // onboarding status hint
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const backToEmail = () => {
    setStep("email"); setError(""); setPassword(""); setConfirm("");
  };

  /** Password sign-in against the pre-Firebase user store (demo/legacy accounts). */
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
      // A public manager sign-up whose email isn't verified yet.
      await firebaseResendAndSignOut();
      setError("Please verify your email to continue. We've sent a new verification link to your inbox — open it, then sign in.");
      return;
    }
    try { localStorage.removeItem(companyKey); } catch { /* ignore */ }
    login(res.data.token, res.data.user);
    navigate("/dashboard");
  };

  const checkEmail = async () => {
    setError("");
    if (!EMAIL_RE.test(email)) { setError("Enter a valid email address."); return; }
    setChecking(true);
    try {
      if (!isFirebaseConfigured) { setStatus("registered"); setStep("password"); return; }
      const { data } = await authApi.onboardingStatus(email);
      setStatus(data.status);
      setStep(data.status === "needs_setup" ? "create" : "password");
    } catch {
      // If the check itself fails, don't trap the user — let them try to sign in.
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
            // No Firebase account and no legacy account for this email.
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
      const { idToken } = await firebaseCreateAccount(email, password);
      try { await exchangeAndFinish(idToken); }
      catch (exErr) { setError(exErr?.response?.data?.detail || SERVER_MSG); }
    } catch (createErr) {
      // They already have a Firebase account (e.g. they used Sign up first). Try
      // signing them in with the same password rather than dead-ending.
      if (createErr?.code === "auth/email-already-in-use") {
        try {
          const result = await firebaseSignInRaw(email, password);
          await exchangeAndFinish(result.idToken);
        } catch {
          setError("An account already exists for this email. Try that password, or reset it from Forgot password.");
        }
      } else {
        setError(firebaseErrorMessage(createErr, "We couldn't set up your account. Please try again."));
      }
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    if (step === "email") return checkEmail();
    if (step === "create") return doCreate();
    return doSignIn();
  };

  const st = strength(password);
  const stColors = ["#e5e7eb", "#ef4444", "#f59e0b", "#f59e0b", "#16a34a"];
  const inputCls =
    "w-full rounded-lg border border-gray-200 pl-9 pr-3 py-2.5 text-sm focus:border-indigo focus:ring-2 focus:ring-indigo/20 outline-none";

  return (
    <div className="min-h-screen flex">
      {/* Left brand panel */}
      <div className="hidden lg:flex w-[45%] bg-navy relative overflow-hidden flex-col justify-between p-12">
        <Link to="/" className="flex items-center gap-2 text-white">
          <Hexagon size={24} className="text-indigo" fill="#4f6ef7" />
          <span className="text-xl font-semibold">HireFlow</span>
        </Link>
        <div className="relative z-10">
          <h2 className="text-white text-4xl font-semibold leading-tight">
            From zero to hired,<br />
            <span className="text-indigo">powered by AI.</span>
          </h2>
          <p className="text-white/55 mt-5 text-[15px] max-w-md leading-relaxed">
            Post a role, rank every applicant, run a visual hiring pipeline, and let AI handle the busywork — whether you're hiring nurses, warehouse staff or engineers.
          </p>
          <div className="flex gap-6 mt-10">
            {[["7", "AI touchpoints"], ["1", "Unified pipeline"], ["Any", "Industry"]].map(([n, l]) => (
              <div key={l}>
                <div className="text-indigo text-3xl font-bold">{n}</div>
                <div className="text-white/45 text-xs mt-1">{l}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="text-white/30 text-xs">© {new Date().getFullYear()} HireFlow</div>
        <div className="absolute -right-24 -bottom-24 w-80 h-80 rounded-full bg-indigo/20 blur-3xl" />
        <div className="absolute right-20 top-20 w-40 h-40 rounded-full bg-purple/20 blur-3xl" />
      </div>

      {/* Right form */}
      <div className="flex-1 flex items-center justify-center bg-gray-50 p-6">
        <div className="w-full max-w-sm animate-fade-in">
          {step === "create" ? (
            <>
              <h1 className="text-2xl font-semibold text-gray-800">Set your password</h1>
              <p className="text-gray-600 text-sm mt-1">Welcome! Choose a password to finish setting up your account for <span className="font-medium text-gray-800">{email}</span>.</p>
            </>
          ) : (
            <>
              <h1 className="text-2xl font-semibold text-gray-800">Welcome back</h1>
              <p className="text-gray-600 text-sm mt-1">Sign in to your hiring dashboard</p>
            </>
          )}

          {error && (
            <div className="mt-5 bg-coral-light text-coral text-sm rounded-lg px-4 py-2.5 leading-relaxed" data-testid="login-error">
              {error}
            </div>
          )}

          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            {/* Email — shown as an editable field on step 1, read-only summary after */}
            {step === "email" ? (
              <div>
                <label className="text-sm font-medium text-gray-700">Email</label>
                <div className="relative mt-1.5">
                  <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)}
                    className={inputCls} placeholder="you@work-email.com" data-testid="login-email"
                  />
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
                  <Link to="/forgot-password" className="text-xs text-indigo font-medium hover:underline" data-testid="goto-forgot">
                    Forgot password?
                  </Link>
                </div>
                <div className="relative mt-1.5">
                  <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    type="password" required autoFocus value={password} onChange={(e) => setPassword(e.target.value)}
                    className={inputCls} placeholder="••••••••" data-testid="login-password"
                  />
                </div>
              </div>
            )}

            {step === "create" && (
              <>
                <div>
                  <label className="text-sm font-medium text-gray-700">New password</label>
                  <div className="relative mt-1.5">
                    <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input
                      type="password" required autoFocus value={password} onChange={(e) => setPassword(e.target.value)}
                      className={inputCls} placeholder="At least 8 characters" data-testid="login-create-password"
                    />
                  </div>
                  {password && (
                    <div className="flex gap-1 mt-2">
                      {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="h-1 flex-1 rounded-full" style={{ background: i <= st ? stColors[st] : "#e5e7eb" }} />
                      ))}
                    </div>
                  )}
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Confirm password</label>
                  <div className="relative mt-1.5">
                    <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                    <input
                      type="password" required value={confirm} onChange={(e) => setConfirm(e.target.value)}
                      className={inputCls} placeholder="••••••••" data-testid="login-confirm"
                    />
                  </div>
                </div>
              </>
            )}

            <Button type="submit" disabled={loading || checking} className="w-full" data-testid="login-submit">
              {loading || checking
                ? <Spinner size={16} />
                : step === "email"
                  ? <>Continue <ArrowRight size={16} /></>
                  : step === "create"
                    ? <>Create account &amp; sign in <ArrowRight size={16} /></>
                    : <>Sign in <ArrowRight size={16} /></>}
            </Button>
          </form>

          <div className="mt-6 text-sm text-gray-600 text-center">
            Don't have an account?{" "}
            <Link to="/signup" className="text-indigo font-medium hover:underline" data-testid="goto-signup">Sign up</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
