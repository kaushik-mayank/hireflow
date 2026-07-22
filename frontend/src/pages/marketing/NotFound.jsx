import { SearchX, ArrowRight } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { LinkButton } from "@/components/marketing";

/**
 * Replaces the previous catch-all, which silently redirected every unknown URL
 * to /dashboard. Auth-aware so a signed-in user who mistypes an app URL is
 * pointed back into the product rather than at the marketing site.
 */
export default function NotFound() {
  const { token } = useAuth();

  return (
    <section className="bg-gray-50 py-28 sm:py-36">
      <div className="mx-auto max-w-md px-6 text-center">
        <div className="mx-auto w-14 h-14 rounded-2xl bg-indigo-light flex items-center justify-center">
          <SearchX size={26} className="text-indigo" />
        </div>
        <p className="mt-6 text-sm font-semibold uppercase tracking-wider text-indigo">404</p>
        <h1 className="mt-2 text-2xl sm:text-3xl font-semibold text-gray-800 tracking-tight">
          This page does not exist
        </h1>
        <p className="mt-3 text-[15px] text-gray-600 leading-relaxed">
          The link may be out of date, or the address may have a typo in it.
        </p>
        <div className="mt-8 flex flex-wrap gap-3 justify-center">
          {token ? (
            <LinkButton to="/dashboard" variant="primary" size="lg">
              Back to dashboard <ArrowRight size={16} />
            </LinkButton>
          ) : (
            <LinkButton to="/" variant="primary" size="lg">
              Back to home <ArrowRight size={16} />
            </LinkButton>
          )}
          <LinkButton to="/coming-soon" variant="secondary" size="lg">
            See the roadmap
          </LinkButton>
        </div>
      </div>
    </section>
  );
}
