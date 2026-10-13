import React from "react";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "indigo" | "success" | "warning" | "danger" | "outline";
  size?: "sm" | "md";
}

export function Badge({
  className = "",
  variant = "default",
  size = "md",
  children,
  ...props
}: BadgeProps) {
  const baseStyles =
    "inline-flex items-center font-medium rounded-full border transition-colors select-none";

  const sizeStyles = {
    sm: "text-[11px] px-2 py-0.5 gap-1",
    md: "text-xs px-2.5 py-1 gap-1.5",
  };

  const variantStyles = {
    default: "bg-slate-800 text-slate-300 border-slate-700/60",
    indigo: "bg-indigo-950/60 text-indigo-300 border-indigo-500/30",
    success: "bg-emerald-950/60 text-emerald-300 border-emerald-500/30",
    warning: "bg-amber-950/60 text-amber-300 border-amber-500/30",
    danger: "bg-rose-950/60 text-rose-300 border-rose-500/30",
    outline: "bg-transparent text-slate-300 border-slate-700",
  };

  return (
    <span
      className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
}
