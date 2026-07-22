import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Hexagon, Mail, Lock, ArrowRight } from "lucide-react";
import { authApi, apiErr } from "@/api";
import { useAuth } from "@/context/AuthContext";
import { Button, Spinner } from "@/components/ui";
import {
  isFirebaseConfigured, firebaseSignIn, firebaseErrorMessage, shouldTryLegacyLogin,
} from "@/lib/firebase";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  /** Password sign-in against the pre-Firebase user store. Still needed for
   *  accounts that existed before Firebase, which have no Firebase identity. */
  const legacyLogin = async () => {
    const res = await authApi.login({ email, password });
    login(res.data.token, res.data.user);
    navigate("/dashboard");
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (!isFirebaseConfigured) {
        await legacyLogin();
        return;
      }

      let idToken;
      try {
        idToken = await firebaseSignIn(email, password);
      } catch (fbErr) {
        // No Firebase account? Could be a pre-Firebase user — try the old path
        // before telling anyone their details are wrong.
        if (shouldTryLegacyLogin(fbErr)) {
          try {
            await legacyLogin();
            return;
          } catch {
            setError("Invalid email or password");
            return;
          }
        }
        setError(firebaseErrorMessage(fbErr, "Could not sign you in"));
        return;
      }

      const res = await authApi.firebase({ id_token: idToken });
      login(res.data.token, res.data.user);
      navigate("/dashboard");
    } catch (err) {
      setError(apiErr(err, "Invalid email or password"));
    } finally {
      setLoading(false);
    }
  };

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
          <h1 className="text-2xl font-semibold text-gray-800">Welcome back</h1>
          <p className="text-gray-600 text-sm mt-1">Sign in to your hiring dashboard</p>

          {error && (
            <div className="mt-5 bg-coral-light text-coral text-sm rounded-lg px-4 py-2.5" data-testid="login-error">
              {error}
            </div>
          )}

          <form onSubmit={submit} className="mt-6 space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700">Email</label>
              <div className="relative mt-1.5">
                <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 pl-9 pr-3 py-2.5 text-sm focus:border-indigo focus:ring-2 focus:ring-indigo/20 outline-none"
                  placeholder="you@work-email.com" data-testid="login-email"
                />
              </div>
            </div>
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
                  type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-gray-200 pl-9 pr-3 py-2.5 text-sm focus:border-indigo focus:ring-2 focus:ring-indigo/20 outline-none"
                  placeholder="••••••••" data-testid="login-password"
                />
              </div>
            </div>
            <Button type="submit" disabled={loading} className="w-full" data-testid="login-submit">
              {loading ? <Spinner size={16} /> : <>Sign in <ArrowRight size={16} /></>}
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
