import { Suspense, useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Menu, X, ArrowRight } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Spinner } from "@/components/ui";
import { Logo, LinkButton, CONTAINER } from "@/components/marketing";

const NAV_LINKS = [
  { to: "/pricing", label: "Pricing" },
  { to: "/reviews", label: "Reviews" },
  { to: "/coming-soon", label: "Coming soon" },
  { to: "/about", label: "About" },
  { to: "/careers", label: "Careers" },
];

const FOOTER_GROUPS = [
  {
    heading: "Product",
    links: [
      { to: "/", label: "Overview" },
      { to: "/pricing", label: "Pricing" },
      { to: "/coming-soon", label: "Coming soon" },
    ],
  },
  {
    heading: "Company",
    links: [
      { to: "/about", label: "About" },
      { to: "/careers", label: "Careers" },
      { to: "/reviews", label: "Reviews" },
    ],
  },
  {
    heading: "Legal",
    links: [{ to: "/privacy", label: "Privacy policy" }],
  },
];

/** Marketing pages are separate documents, so each should start at the top. */
function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

const navLinkClass = ({ isActive }) =>
  `text-sm transition-colors duration-150 ${
    isActive ? "text-gray-800 font-medium" : "text-gray-600 hover:text-gray-800"
  }`;

function MarketingHeader() {
  const { token } = useAuth();
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();

  // Close the mobile menu whenever navigation happens.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-gray-200">
      <div className={`${CONTAINER} flex items-center justify-between h-16`}>
        <Logo />

        <nav className="hidden md:flex items-center gap-7" aria-label="Main">
          {NAV_LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} className={navLinkClass}>
              {l.label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden md:flex items-center gap-2">
          {token ? (
            <LinkButton to="/dashboard" variant="primary" data-testid="marketing-dashboard">
              Go to dashboard <ArrowRight size={15} />
            </LinkButton>
          ) : (
            <>
              <LinkButton to="/login" variant="ghost" data-testid="marketing-login">
                Log in
              </LinkButton>
              <LinkButton to="/signup" variant="primary" data-testid="marketing-register">
                Register
              </LinkButton>
            </>
          )}
        </div>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="md:hidden p-2 -mr-2 rounded-md text-gray-700 hover:bg-gray-100"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          data-testid="marketing-menu-toggle"
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {open && (
        <div className="md:hidden border-t border-gray-200 bg-white animate-fade-in">
          <nav className={`${CONTAINER} py-4 flex flex-col gap-1`} aria-label="Mobile">
            {NAV_LINKS.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) =>
                  `py-2.5 text-sm rounded-md px-2 -mx-2 ${
                    isActive ? "text-gray-800 font-medium bg-gray-50" : "text-gray-600 hover:bg-gray-50"
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
            <div className="flex flex-col gap-2 pt-3 mt-2 border-t border-gray-200">
              {token ? (
                <LinkButton to="/dashboard" variant="primary" className="w-full">
                  Go to dashboard <ArrowRight size={15} />
                </LinkButton>
              ) : (
                <>
                  <LinkButton to="/login" variant="secondary" className="w-full">
                    Log in
                  </LinkButton>
                  <LinkButton to="/signup" variant="primary" className="w-full">
                    Register
                  </LinkButton>
                </>
              )}
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}

function MarketingFooter() {
  return (
    <footer className="bg-navy">
      <div className={`${CONTAINER} py-14`}>
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <Logo tone="light" />
            <p className="mt-3.5 text-white/45 text-sm leading-relaxed max-w-xs">
              AI hiring software for every kind of role — from the ward and the warehouse floor to the
              workshop and the office.
            </p>
          </div>

          {FOOTER_GROUPS.map((group) => (
            <div key={group.heading}>
              <div className="text-[11px] uppercase tracking-wider text-white/35 font-semibold">
                {group.heading}
              </div>
              <ul className="mt-4 space-y-2.5">
                {group.links.map((l) => (
                  <li key={l.to + l.label}>
                    <Link to={l.to} className="text-sm text-white/55 hover:text-white transition-colors duration-150">
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}

          <div>
            <div className="text-[11px] uppercase tracking-wider text-white/35 font-semibold">Get started</div>
            <ul className="mt-4 space-y-2.5">
              <li>
                <Link to="/signup" className="text-sm text-white/55 hover:text-white transition-colors duration-150">
                  Create an account
                </Link>
              </li>
              <li>
                <Link to="/login" className="text-sm text-white/55 hover:text-white transition-colors duration-150">
                  Log in
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 pt-6 border-t border-white/10 flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
          <div className="text-white/30 text-xs">
            © {new Date().getFullYear()} HireFlow. All rights reserved.
          </div>
          <div className="text-white/30 text-xs">
            Early access — features and pricing are still being finalised.
          </div>
        </div>
      </div>
    </footer>
  );
}

function PageFallback() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <Spinner size={24} className="text-indigo" />
    </div>
  );
}

export default function MarketingLayout() {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      <ScrollToTop />
      <MarketingHeader />
      <main className="flex-1">
        {/* Inner boundary so the header and footer stay mounted while the next
            page chunk loads, instead of the whole shell flashing. */}
        <Suspense fallback={<PageFallback />}>
          <Outlet />
        </Suspense>
      </main>
      <MarketingFooter />
    </div>
  );
}
