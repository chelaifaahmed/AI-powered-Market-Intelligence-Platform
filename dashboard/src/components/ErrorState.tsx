import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorStateProps {
  error?: Error | unknown;
  onRetry?: () => void;
  title?: string;
}

export default function ErrorState({
  error,
  onRetry,
  title = "Failed to load data",
}: ErrorStateProps) {
  const message =
    error instanceof Error ? error.message : "An unexpected error occurred";

  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50 mb-4">
        <AlertTriangle className="h-6 w-6 text-red-500" strokeWidth={1.5} />
      </div>
      <h3 className="text-sm font-semibold text-slate-700 mb-1">{title}</h3>
      <p className="text-xs text-slate-500 max-w-xs font-mono bg-slate-50 px-3 py-2 rounded-lg border border-slate-100 mt-2">
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 btn-ghost text-sm"
        >
          <RefreshCw className="h-4 w-4" />
          Retry
        </button>
      )}
    </div>
  );
}
