import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { Spinner } from "@/components/ui";
/* Dashboard stays eager: it is where every sign-in lands, so deferring it
   would only trade bundle size for a spinner on the most common path. */
import Dashboard from "@/pages/Dashboard";

/* Everything past the dashboard is deferred. Reports matters most here — it is
   the only eagerly-loaded page that pulls in recharts, so leaving it in the
   entry bundle meant every user downloaded the entire charting library on
   sign-in whether or not they ever opened a chart. */
const Jobs = lazy(() => import("@/pages/Jobs"));
const JobCreate = lazy(() => import("@/pages/JobCreate"));
const JobDetail = lazy(() => import("@/pages/JobDetail"));
const CandidateBoard = lazy(() => import("@/pages/CandidateBoard"));
const CandidateDetail = lazy(() => import("@/pages/CandidateDetail"));
const Reports = lazy(() => import("@/pages/Reports"));

/* The admin panel is reachable by exactly one account on the platform, so
   every HR user was downloading six pages they can never open. Lazy-loaded. */
const AdminDashboard = lazy(() => import("@/pages/admin/AdminDashboard"));
const AdminUsers = lazy(() => import("@/pages/admin/AdminUsers"));
const AdminResumes = lazy(() => import("@/pages/admin/AdminResumes"));
const AdminAnalytics = lazy(() => import("@/pages/admin/AdminAnalytics"));
const AdminAIUsage = lazy(() => import("@/pages/admin/AdminAIUsage"));
const AdminFeedback = lazy(() => import("@/pages/admin/AdminFeedback"));

/* Support pages are opened rarely and cost nothing to defer. */
const Feedback = lazy(() => import("@/pages/Feedback"));

/* Auth pages are lazy-loaded so the Firebase SDK — which only they use — stays
   out of the authenticated app's bundle. */
const Login = lazy(() => import("@/pages/Login"));
const Signup = lazy(() => import("@/pages/Signup"));
const ForgotPassword = lazy(() => import("@/pages/ForgotPassword"));

/* The public marketing site is lazy-loaded so it stays out of the
   authenticated app's bundle — a signed-in user never downloads it. */
const MarketingLayout = lazy(() => import("@/pages/marketing/MarketingLayout"));
const Home = lazy(() => import("@/pages/marketing/Home"));
const Pricing = lazy(() => import("@/pages/marketing/Pricing"));
const About = lazy(() => import("@/pages/marketing/About"));
const Careers = lazy(() => import("@/pages/marketing/Careers"));
const Reviews = lazy(() => import("@/pages/marketing/Reviews"));
const Privacy = lazy(() => import("@/pages/marketing/Privacy"));
const ComingSoon = lazy(() => import("@/pages/marketing/ComingSoon"));
const NotFound = lazy(() => import("@/pages/marketing/NotFound"));

function FullScreenLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Spinner size={28} className="text-indigo" />
    </div>
  );
}

function PrivateRoute({ children }) {
  const { token, loading } = useAuth();
  if (loading) return <FullScreenLoader />;
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

function PublicRoute({ children }) {
  const { token, loading } = useAuth();
  if (loading) return <FullScreenLoader />;
  if (token) return <Navigate to="/dashboard" replace />;
  return children;
}

function AdminRoute({ children }) {
  const { token, user, loading } = useAuth();
  if (loading) return <FullScreenLoader />;
  if (!token) return <Navigate to="/login" replace />;
  if (user?.role !== "admin") return <Navigate to="/dashboard" replace />;
  return children;
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public marketing site. Reachable signed in or out — the header swaps
          Log in / Register for a link back to the dashboard. */}
      <Route element={<MarketingLayout />}>
        <Route path="/" element={<Home />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/about" element={<About />} />
        <Route path="/careers" element={<Careers />} />
        <Route path="/reviews" element={<Reviews />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/coming-soon" element={<ComingSoon />} />
        <Route path="*" element={<NotFound />} />
      </Route>

      <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
      <Route path="/signup" element={<PublicRoute><Signup /></PublicRoute>} />
      <Route path="/forgot-password" element={<PublicRoute><ForgotPassword /></PublicRoute>} />

      <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
      <Route path="/jobs" element={<PrivateRoute><Jobs /></PrivateRoute>} />
      <Route path="/jobs/create" element={<PrivateRoute><JobCreate /></PrivateRoute>} />
      <Route path="/jobs/:id" element={<PrivateRoute><JobDetail /></PrivateRoute>} />
      <Route path="/jobs/:id/board" element={<PrivateRoute><CandidateBoard /></PrivateRoute>} />
      <Route path="/candidates/:id" element={<PrivateRoute><CandidateDetail /></PrivateRoute>} />
      <Route path="/reports" element={<PrivateRoute><Reports /></PrivateRoute>} />
      <Route path="/feedback" element={<PrivateRoute><Feedback /></PrivateRoute>} />

      <Route path="/admin" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
      <Route path="/admin/users" element={<AdminRoute><AdminUsers /></AdminRoute>} />
      <Route path="/admin/resumes" element={<AdminRoute><AdminResumes /></AdminRoute>} />
      <Route path="/admin/analytics" element={<AdminRoute><AdminAnalytics /></AdminRoute>} />
      <Route path="/admin/ai-usage" element={<AdminRoute><AdminAIUsage /></AdminRoute>} />
      <Route path="/admin/feedback" element={<AdminRoute><AdminFeedback /></AdminRoute>} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<FullScreenLoader />}>
          <AppRoutes />
        </Suspense>
        <Toaster position="bottom-right" richColors closeButton />
      </BrowserRouter>
    </AuthProvider>
  );
}
