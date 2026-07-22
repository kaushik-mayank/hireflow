import { Component } from "react";
import { AlertTriangle } from "lucide-react";

/**
 * Catches render errors so one broken component cannot blank the entire app.
 *
 * Without this, any thrown error during render unmounts the whole React tree
 * and the user sees a white page with no explanation and no way back.
 *
 * Must be a class — React has no hook equivalent of componentDidCatch.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Left as console output deliberately: there is no error-reporting service
    // wired up yet, and swallowing this silently would make support harder.
    console.error("Unhandled render error:", error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
        <div className="w-full max-w-md text-center">
          <div className="mx-auto w-14 h-14 rounded-2xl bg-coral-light flex items-center justify-center">
            <AlertTriangle size={26} className="text-coral" />
          </div>
          <h1 className="mt-5 text-xl font-semibold text-gray-800">Something went wrong</h1>
          <p className="mt-2 text-sm text-gray-600 leading-relaxed">
            This page hit an unexpected error. Reloading usually clears it. If it keeps
            happening, please send us a bug report from the Support section.
          </p>
          <div className="mt-7 flex flex-wrap gap-3 justify-center">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo px-4 py-2.5 text-sm font-medium text-white shadow-soft transition-all duration-150 hover:brightness-110 active:translate-y-px"
            >
              Reload the page
            </button>
            <button
              type="button"
              onClick={() => { window.location.href = "/dashboard"; }}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-white text-gray-700 border border-gray-200 px-4 py-2.5 text-sm font-medium transition-all duration-150 hover:bg-gray-50 active:translate-y-px"
            >
              Back to dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }
}
