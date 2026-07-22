import { useEffect } from "react";
import { X, Loader2, Sparkles } from "lucide-react";
import { STAGE_COLORS, scoreColor, initials } from "@/constants";

export function Button({ variant = "primary", className = "", children, ...props }) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg font-medium text-sm transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed active:translate-y-px";
  const variants = {
    primary: "bg-indigo text-white px-4 py-2 hover:brightness-110 shadow-soft",
    secondary: "bg-white text-gray-700 border border-gray-200 px-4 py-2 hover:bg-gray-50",
    ghost: "text-gray-600 px-3 py-2 hover:bg-gray-100",
    danger: "bg-coral text-white px-4 py-2 hover:brightness-110",
    subtle: "bg-gray-100 text-gray-700 px-4 py-2 hover:bg-gray-200",
  };
  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function AIButton({ loading, className = "", children, ...props }) {
  return (
    <button
      className={`ai-btn inline-flex items-center justify-center gap-2 rounded-lg font-medium text-sm px-4 py-2 ${className}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
      {children}
    </button>
  );
}

export function Spinner({ size = 18, className = "" }) {
  return <Loader2 size={size} className={`animate-spin ${className}`} />;
}

export function Card({ className = "", children, ...props }) {
  return (
    <div className={`bg-white border border-gray-200 rounded-xl shadow-soft ${className}`} {...props}>
      {children}
    </div>
  );
}

export function Avatar({ name, size = 36, color = "#4f6ef7" }) {
  return (
    <div
      className="flex items-center justify-center rounded-full font-semibold text-white shrink-0"
      style={{ width: size, height: size, background: color, fontSize: size * 0.38 }}
    >
      {initials(name)}
    </div>
  );
}

export function StageBadge({ stage, className = "" }) {
  const c = STAGE_COLORS[stage] || STAGE_COLORS["Applied"];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${className}`}
      style={{ background: c.bg, color: c.color }}
    >
      {stage}
    </span>
  );
}

export function ScoreBadge({ score, large = false }) {
  const c = scoreColor(score);
  if (large) {
    return (
      <span className="inline-flex items-baseline font-bold" style={{ color: c.color }}>
        <span className="text-5xl leading-none">{score ?? "—"}</span>
        {score != null && <span className="text-lg ml-0.5">/100</span>}
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center justify-center rounded-md px-2 py-0.5 text-xs font-bold min-w-[34px]"
      style={{ background: c.bg, color: c.color }}
    >
      {score ?? "—"}
    </span>
  );
}

export function Pill({ children, tone = "gray" }) {
  const tones = {
    green: "bg-green-light text-green",
    red: "bg-coral-light text-coral",
    amber: "bg-amber-light text-[#92400e]",
    gray: "bg-gray-100 text-gray-700",
  };
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function Modal({ open, onClose, title, children, width = "max-w-2xl", footer }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose?.();
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-navy/40 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div
        className={`relative bg-white rounded-2xl shadow-lift w-full ${width} max-h-[88vh] flex flex-col animate-fade-in`}
        data-testid="modal"
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h3 className="font-semibold text-gray-800 text-lg">{title}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 p-1 rounded-md hover:bg-gray-100" data-testid="modal-close">
            <X size={18} />
          </button>
        </div>
        <div className="px-6 py-5 overflow-y-auto">{children}</div>
        {footer && <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, subtitle, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-4">
      {Icon && (
        <div className="w-14 h-14 rounded-2xl bg-indigo-light flex items-center justify-center mb-4">
          <Icon size={26} className="text-indigo" />
        </div>
      )}
      <h3 className="font-semibold text-gray-800 text-base">{title}</h3>
      {subtitle && <p className="text-gray-600 text-sm mt-1 max-w-sm">{subtitle}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Skeleton({ className = "" }) {
  return <div className={`skeleton ${className}`} />;
}

export function ProgressBar({ value, max, color = "#16a34a" }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}
