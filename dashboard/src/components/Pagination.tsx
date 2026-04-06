import { ChevronLeft, ChevronRight } from "lucide-react";
import clsx from "clsx";

interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  onOffsetChange: (offset: number) => void;
}

export default function Pagination({ total, limit, offset, onOffsetChange }: PaginationProps) {
  const page = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + limit, total);

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100">
      <p className="text-xs text-slate-500">
        {total === 0 ? "No results" : `Showing ${start}–${end} of ${total.toLocaleString()}`}
      </p>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
          disabled={page <= 1}
          className={clsx(
            "p-1.5 rounded-md transition-colors",
            page <= 1
              ? "text-slate-300 cursor-not-allowed"
              : "text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          )}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="text-xs text-slate-600 px-2 font-medium tabular-nums">
          {page} / {totalPages}
        </span>
        <button
          onClick={() => onOffsetChange(Math.min((totalPages - 1) * limit, offset + limit))}
          disabled={page >= totalPages}
          className={clsx(
            "p-1.5 rounded-md transition-colors",
            page >= totalPages
              ? "text-slate-300 cursor-not-allowed"
              : "text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          )}
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
