import { useState } from "react";
import { Link } from "react-router-dom";
import { Hexagon, Mail, ArrowLeft, MailCheck } from "lucide-react";
import { Button, Spinner } from "@/components/ui";
import { isFirebaseConfigured, firebaseSendPasswordReset, firebaseErrorMessage } from "@/lib/firebase";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await firebaseSendPasswordReset(email);
      setSent(true);
    } catch (err) {
      // Firebase returns auth/user-not-found for unknown addresses, which would
      // let anyone probe for registered emails. Show the same confirmation
      // either way and only surface genuine failures.
      if (err?.code === "auth/user-not-found") {
        setSent(true);
      } else {
        setError(firebaseErrorMessage(err, "Could not send the reset email. Please try again."));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex w-[45%] bg-navy relative overflow-hidden flex-col justify-between p-12">
        <Link to="/" className="flex items-center gap-2 text-white">
          <Hexagon size={24} className="text-indigo" fill="#4f6ef7" />
          <span className="text-xl font-semibold">HireFlow</span>
        </Link>
        <div className="relative z-10">
          <h2 className="text-white text-4xl font-semibold leading-tight">
            Locked out?<br /><span className="text-indigo">Back in a minute.</span>
          </h2>
          <p className="text-white/55 mt-5 text-[15px] max-w-md leading-relaxed">
            We'll email you a secure link to set a new password. It expires shortly after it's sent.
          </p>
        </div>
        <div className="text-white/30 text-xs">© {new Date().getFullYear()} HireFlow</div>
        <div className="absolute -right-24 -bottom-24 w-80 h-80 rounded-full bg-indigo/20 blur-3xl" />
      </div>

      <div className="flex-1 flex items-center justify-center bg-gray-50 p-6">
        <div className="w-full max-w-sm animate-fade-in">
          {sent ? (
            <div data-testid="forgot-sent">
              <div className="w-14 h-14 rounded-2xl bg-green-light flex items-center justify-center">
                <MailCheck size={26} className="text-green" />
              </div>
              <h1 className="mt-5 text-2xl font-semibold text-gray-800">Check your email</h1>
              <p className="text-gray-600 text-sm mt-2 leading-relaxed">
                If an account exists for <span className="font-medium text-gray-800">{email}</span>, we've
                sent a link to reset your password. It may take a minute to arrive — check your spam folder too.
              </p>
              <Link
                to="/login"
                className="mt-7 inline-flex items-center justify-center gap-2 rounded-lg bg-indigo px-4 py-2.5 text-sm font-medium text-white shadow-soft transition-all duration-150 hover:brightness-110 active:translate-y-px w-full"
              >
                Back to sign in
              </Link>
            </div>
          ) : (
            <>
              <h1 className="text-2xl font-semibold text-gray-800">Reset your password</h1>
              <p className="text-gray-600 text-sm mt-1">
                Enter your email and we'll send you a link to set a new one.
              </p>

              {!isFirebaseConfigured && (
                <div className="mt-5 rounded-lg border border-amber bg-amber-light px-4 py-3 text-sm text-[#92400e] leading-relaxed" data-testid="forgot-unavailable">
                  Password reset isn't available on this environment yet. Please contact your administrator
                  to have your password reset.
                </div>
              )}

              {error && (
                <div className="mt-5 bg-coral-light text-coral text-sm rounded-lg px-4 py-2.5" data-testid="forgot-error">
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
                      disabled={!isFirebaseConfigured}
                      className="w-full rounded-lg border border-gray-200 pl-9 pr-3 py-2.5 text-sm focus:border-indigo focus:ring-2 focus:ring-indigo/20 outline-none disabled:bg-gray-100 disabled:cursor-not-allowed"
                      placeholder="you@work-email.com" data-testid="forgot-email"
                    />
                  </div>
                </div>
                <Button type="submit" disabled={loading || !isFirebaseConfigured} className="w-full" data-testid="forgot-submit">
                  {loading ? <Spinner size={16} /> : "Send reset link"}
                </Button>
              </form>
            </>
          )}

          <div className="mt-6 text-sm text-center">
            <Link to="/login" className="inline-flex items-center gap-1.5 text-gray-600 hover:text-gray-800">
              <ArrowLeft size={14} /> Back to sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
