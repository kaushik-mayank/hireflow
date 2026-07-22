import { NavLink, useNavigate } from "react-router-dom";
import { LayoutDashboard, Briefcase, BarChart3, Users, FileText, Activity, DollarSign, LogOut, Hexagon, Shield } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Avatar } from "@/components/ui";

const navItem = ({ isActive }) =>
  `flex items-center gap-3 text-[13.5px] rounded-lg px-3.5 py-2.5 mx-2 my-px transition-all duration-150 ${
    isActive
      ? "bg-indigo/25 text-white"
      : "text-white/55 hover:bg-white/[0.07] hover:text-white/85"
  }`;

export function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-60 bg-navy flex flex-col z-30" data-testid="sidebar">
      <div className="px-5 pt-6 pb-5">
        <div className="flex items-center gap-2 text-white">
          <Hexagon size={20} className="text-indigo" fill="#4f6ef7" />
          <span className="text-[17px] font-semibold tracking-tight">HireFlow</span>
          {isAdmin && (
            <span
              className="ml-auto rounded-md bg-purple/25 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-purple-light"
              data-testid="admin-badge"
              title="You are signed in as the platform administrator"
            >
              Admin
            </span>
          )}
        </div>
        <div className="text-[11px] uppercase tracking-wider text-white/35 mt-1 ml-7">AI Hiring Platform</div>
      </div>

      <nav className="flex-1 overflow-y-auto py-2">
        <div className="text-[10px] uppercase tracking-wider text-white/25 px-5 py-2 mt-1">Hiring</div>
        <NavLink to="/dashboard" className={navItem} data-testid="nav-dashboard">
          <LayoutDashboard size={17} /> Dashboard
        </NavLink>
        <NavLink to="/jobs" className={navItem} data-testid="nav-jobs">
          <Briefcase size={17} /> Jobs
        </NavLink>
        <NavLink to="/reports" className={navItem} data-testid="nav-reports">
          <BarChart3 size={17} /> Reports
        </NavLink>

        {isAdmin && (
          <>
            <div className="mt-5 mx-2 border-t border-purple/25" />
            <div className="text-[10px] uppercase tracking-wider text-purple-light/70 px-5 py-2 mt-2 flex items-center gap-1.5">
              <Shield size={11} /> Platform Admin
            </div>
            <NavLink to="/admin" end className={navItem} data-testid="nav-admin-dashboard">
              <LayoutDashboard size={17} /> Admin Dashboard
            </NavLink>
            <NavLink to="/admin/users" className={navItem} data-testid="nav-admin-users">
              <Users size={17} /> User Management
            </NavLink>
            <NavLink to="/admin/resumes" className={navItem} data-testid="nav-admin-resumes">
              <FileText size={17} /> Uploaded Resumes
            </NavLink>
            <NavLink to="/admin/analytics" className={navItem} data-testid="nav-admin-analytics">
              <Activity size={17} /> System Analytics
            </NavLink>
            <NavLink to="/admin/ai-usage" className={navItem} data-testid="nav-admin-ai">
              <DollarSign size={17} /> AI Usage & Cost
            </NavLink>
          </>
        )}
      </nav>

      <div className="border-t border-white/10 p-3">
        <div className="flex items-center gap-3 px-2 py-2">
          <Avatar name={user?.name} size={34} />
          <div className="min-w-0 flex-1">
            <div className="text-white text-[13px] font-medium truncate">{user?.name}</div>
            <div className="text-white/40 text-[11px] truncate">{user?.company || user?.email}</div>
          </div>
          <button onClick={handleLogout} className="text-white/45 hover:text-white p-1.5 rounded-md hover:bg-white/10" data-testid="logout-btn" title="Log out">
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </aside>
  );
}

export function Topbar({ title, subtitle, actions }) {
  return (
    <div className="sticky top-0 z-20 bg-white border-b border-gray-200">
      <div className="flex items-center justify-between px-9 py-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-800">{title}</h1>
          {subtitle && <p className="text-sm text-gray-600 mt-0.5">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">{actions}</div>
      </div>
    </div>
  );
}

export default function Layout({ children, fullWidth = false }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />
      <main className="ml-60 min-h-screen">{children}</main>
    </div>
  );
}

export function PageBody({ children, fullWidth = false }) {
  if (fullWidth) return <div className="p-6">{children}</div>;
  return <div className="max-w-[980px] mx-auto px-9 py-7">{children}</div>;
}
