import { AlertTriangle, RefreshCcw } from "lucide-react";
import { getApiErrorMessage, getApiErrorStatus, isServerApiError } from "@/lib/api";

interface ApiServerErrorBannerProps {
  errors: unknown[];
  onRetry: () => void | Promise<void>;
  title?: string;
  className?: string;
}

export function ApiServerErrorBanner({ errors, onRetry, title, className = "" }: ApiServerErrorBannerProps) {
  const serverError = errors.find((err) => isServerApiError(err));
  if (!serverError) return null;

  const status = getApiErrorStatus(serverError);
  const message = getApiErrorMessage(serverError);

  return (
    <div className={`rounded-xl border border-rose-400/40 bg-rose-500/12 px-4 py-3 text-rose-100 ${className}`.trim()}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <AlertTriangle size={16} className="shrink-0" />
            {title || "Ошибка сервера"}
            {status ? <span className="opacity-85">({status})</span> : null}
          </p>
          <p className="mt-1 text-xs text-rose-100/90 break-words">
            {message}
          </p>
        </div>
        <button
          className="shrink-0 rounded-lg border border-rose-300/50 bg-rose-500/20 px-3 py-1.5 text-xs font-semibold text-rose-50 hover:bg-rose-500/30"
          onClick={onRetry}
        >
          <span className="inline-flex items-center gap-1.5">
            <RefreshCcw size={12} />
            Попробовать снова
          </span>
        </button>
      </div>
    </div>
  );
}
