import React from "react";
import { IconAlertTriangle } from "./icons";
import { ApiErrorDetail } from "../../lib/types";

export interface ErrorAlertProps {
  title?: string;
  message: string;
  code?: string;
  details?: ApiErrorDetail[];
  className?: string;
  onDismiss?: () => void;
}

export function ErrorAlert({
  title = "Error Encountered",
  message,
  code,
  details,
  className = "",
  onDismiss,
}: ErrorAlertProps) {
  return (
    <div
      role="alert"
      className={`rounded-lg border border-rose-500/30 bg-rose-950/30 p-4 text-slate-200 ${className}`}
    >
      <div className="flex items-start gap-3">
        <IconAlertTriangle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-rose-200">{title}</h4>
            {code && (
              <span className="font-mono text-[10px] uppercase tracking-wider text-rose-400 bg-rose-900/40 px-1.5 py-0.5 rounded border border-rose-700/50">
                {code}
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-rose-300 leading-relaxed">{message}</p>

          {details && details.length > 0 && (
            <ul className="mt-2.5 space-y-1 text-xs text-rose-300/90 list-disc list-inside">
              {details.map((item, idx) => (
                <li key={idx}>
                  {item.field ? <strong className="font-mono text-rose-200">{item.field}: </strong> : null}
                  {item.issue}
                </li>
              ))}
            </ul>
          )}
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="text-slate-400 hover:text-slate-200 p-1 rounded-md transition-colors"
            aria-label="Dismiss error"
          >
            <span aria-hidden="true">&times;</span>
          </button>
        )}
      </div>
    </div>
  );
}
