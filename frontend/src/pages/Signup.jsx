import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Hexagon, ArrowRight } from "lucide-react";
import { authApi, apiErr } from "@/api";
import { useAuth } from "@/context/AuthContext";
import { Button, Spinner } from "@/components/ui";
import { isFirebaseConfigured, firebaseSignUp, firebaseErrorMessage } from "@/lib/firebase";

function strength(pw) {
  let s = 0;
  if (pw.length >= 8) s++;
  if (/[A-Z]/.test(pw)) s++;
  if (/[0-9]/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  return s;
}

export default function Signup() {
  // NOTE: there is deliberately no `role` here. Public signup always creates a
  // standard HR account; the server ignores any role sent by a client.
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "", company: "" });
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const validate = () => {
    const er = {};
    if (!form.name.trim()) er.name = "Full name is required";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) er.email = "Enter a valid email";
    if (form.password.length < 8) er.password = "Password must be at least 8 characters";
    if (form.password !== form.confirm) er.confirm = "Passwords do not match";
    setErrors(er);
    return Object.keys(er).length === 0;
  };

  const submit = async (e) => {
    e.preventDefault();
    setServerError("");
    if (!validate()) return;
    setLoading(true);

    try {
      if (isFirebaseConfigured) {
        let idToken;
        try {
          idToken = await firebaseSignUp(form.email, form.password);
        } catch (fbErr) {
          setServerError(firebaseErrorMessage(fbErr, "Could not create account"));
          return;
        }
        const res = await authApi.firebase({
          id_token: idToken, name: form.name, company: form.company,
        });
        login(res.data.token, res.data.user);
      } else {
        const res = await authApi.signup({
          name: form.name, email: form.email, password: form.password, company: form.company,
        });
        login(res.data.token, res.data.user);
      }
      navigate("/dashboard");
    } catch (err) {
      setServerError(apiErr(err, "Could not create account"));
    } finally {
      setLoading(false);
    }
  };

  const st = strength(form.password);
  const stColors = ["#e5e7eb", "#ef4444", "#f59e0b", "#f59e0b", "#16a34a"];

  const field = (k) => `w-full rounded-lg border px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo/20 ${errors[k] ? "border-coral" : "border-gray-200 focus:border-indigo"}`;

  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex w-[45%] bg-navy relative overflow-hidden flex-col justify-between p-12">
        <Link to="/" className="flex items-center gap-2 text-white">
          <Hexagon size={24} className="text-indigo" fill="#4f6ef7" />
          <span className="text-xl font-semibold">HireFlow</span>
        </Link>
        <div className="relative z-10">
          <h2 className="text-white text-4xl font-semibold leading-tight">Build your hiring<br /><span className="text-indigo">command center.</span></h2>
          <p className="text-white/55 mt-5 text-[15px] max-w-md leading-relaxed">Set how many people you need, upload the applications, and watch AI rank and move candidates through your pipeline — for any role, in any industry.</p>
        </div>
        <div className="text-white/30 text-xs">© {new Date().getFullYear()} HireFlow</div>
        <div className="absolute -right-24 -bottom-24 w-80 h-80 rounded-full bg-indigo/20 blur-3xl" />
      </div>

      <div className="flex-1 flex items-center justify-center bg-gray-50 p-6 overflow-y-auto">
        <div className="w-full max-w-sm py-8 animate-fade-in">
          <h1 className="text-2xl font-semibold text-gray-800">Create your account</h1>
          <p className="text-gray-600 text-sm mt-1">Start hiring smarter in minutes</p>

          {serverError && <div className="mt-5 bg-coral-light text-coral text-sm rounded-lg px-4 py-2.5" data-testid="signup-error">{serverError}</div>}

          <form onSubmit={submit} className="mt-6 space-y-3.5">
            <div>
              <label className="text-sm font-medium text-gray-700">Full Name</label>
              <input value={form.name} onChange={set("name")} className={`mt-1.5 ${field("name")}`} placeholder="Alex Morgan" data-testid="signup-name" />
              {errors.name && <p className="text-xs text-coral mt-1">{errors.name}</p>}
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Email</label>
              <input type="email" value={form.email} onChange={set("email")} className={`mt-1.5 ${field("email")}`} placeholder="you@work-email.com" data-testid="signup-email" />
              {errors.email && <p className="text-xs text-coral mt-1">{errors.email}</p>}
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Organisation</label>
              <input value={form.company} onChange={set("company")} className={`mt-1.5 ${field("company")}`} placeholder="Company, clinic, site or agency" data-testid="signup-company" />
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-sm font-medium text-gray-700">Password</label>
                <input type="password" value={form.password} onChange={set("password")} className={`mt-1.5 ${field("password")}`} placeholder="••••••••" data-testid="signup-password" />
              </div>
              <div className="flex-1">
                <label className="text-sm font-medium text-gray-700">Confirm</label>
                <input type="password" value={form.confirm} onChange={set("confirm")} className={`mt-1.5 ${field("confirm")}`} placeholder="••••••••" data-testid="signup-confirm" />
              </div>
            </div>
            {form.password && (
              <div className="flex gap-1">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-1 flex-1 rounded-full" style={{ background: i <= st ? stColors[st] : "#e5e7eb" }} />
                ))}
              </div>
            )}
            {errors.password && <p className="text-xs text-coral">{errors.password}</p>}
            {errors.confirm && <p className="text-xs text-coral">{errors.confirm}</p>}

            <Button type="submit" disabled={loading} className="w-full" data-testid="signup-submit">
              {loading ? <Spinner size={16} /> : <>Create account <ArrowRight size={16} /></>}
            </Button>
          </form>

          <p className="mt-4 text-xs text-gray-600 text-center leading-relaxed">
            By creating an account you agree to our{" "}
            <Link to="/privacy" className="text-indigo hover:underline">Privacy Policy</Link>.
          </p>

          <div className="mt-5 text-sm text-gray-600 text-center">
            Already have an account?{" "}
            <Link to="/login" className="text-indigo font-medium hover:underline" data-testid="goto-login">Sign in</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
