import { useState, useEffect, useCallback, useRef } from "react";
import { useServerEvents, ServerEvent, ConnectionStatus } from "../hooks/useServerEvents";
import { Zap, CheckCircle, RefreshCw } from "lucide-react";

interface Toast {
  id: number;
  message: string;
  type: "signal" | "pipeline" | "data";
}

let _toastId = 0;

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: number) => void }) {
  useEffect(() => {
    const t = setTimeout(() => onDismiss(toast.id), 5000);
    return () => clearTimeout(t);
  }, [toast.id, onDismiss]);

  const colors = {
    signal: { bg: "#1a1200", border: "#92400e", text: "#F59E0B", icon: "#F59E0B" },
    pipeline: { bg: "#0a1628", border: "#1e3a5f", text: "#60A5FA", icon: "#3B82F6" },
    data: { bg: "#0a1a0a", border: "#166534", text: "#4ADE80", icon: "#22C55E" },
  };
  const c = colors[toast.type];

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 14px",
        borderRadius: 8,
        backgroundColor: c.bg,
        border: `1px solid ${c.border}`,
        boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
        cursor: "pointer",
        animation: "slideIn 200ms ease",
        minWidth: 260,
        maxWidth: 340,
      }}
      onClick={() => onDismiss(toast.id)}
    >
      {toast.type === "signal" && <Zap size={14} style={{ color: c.icon, flexShrink: 0 }} />}
      {toast.type === "pipeline" && <CheckCircle size={14} style={{ color: c.icon, flexShrink: 0 }} />}
      {toast.type === "data" && <RefreshCw size={14} style={{ color: c.icon, flexShrink: 0 }} />}
      <span style={{ fontSize: 12, fontWeight: 500, color: c.text, lineHeight: 1.4 }}>
        {toast.message}
      </span>
    </div>
  );
}

function ToastContainer({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  if (toasts.length === 0) return null;
  return (
    <div
      style={{
        position: "fixed",
        bottom: 24,
        right: 24,
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function StatusDot({ status, pulsing }: { status: ConnectionStatus; pulsing: boolean }) {
  const color =
    status === "connected" ? "#22C55E" :
    status === "connecting" ? "#F59E0B" :
    "#6B7280";

  return (
    <div style={{ position: "relative", width: 8, height: 8, flexShrink: 0 }}>
      <span
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          backgroundColor: color,
          opacity: pulsing ? 0.4 : 0,
          animation: pulsing ? "ripple 1.2s ease-out" : "none",
        }}
      />
      <span
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          backgroundColor: color,
        }}
      />
    </div>
  );
}

export default function LiveIndicator() {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [pulsing, setPulsing] = useState(false);
  const pulseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const triggerPulse = useCallback(() => {
    setPulsing(true);
    if (pulseTimer.current) clearTimeout(pulseTimer.current);
    pulseTimer.current = setTimeout(() => setPulsing(false), 1400);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const handleEvent = useCallback(
    (event: ServerEvent) => {
      triggerPulse();
      let msg = "";
      let type: Toast["type"] = "pipeline";

      if (event.type === "opportunity_update" && event.strong != null) {
        msg = `Signals updated — ${event.strong} strong${event.top_entity ? ` · Top: ${event.top_entity}` : ""}`;
        type = "signal";
      } else if (event.type === "pipeline_complete") {
        msg = `Pipeline complete — ${event.component ?? "unknown"} · ${event.records ?? 0} records`;
        type = "pipeline";
      } else if (event.type === "data_update" && event.count != null) {
        msg = `+${event.count} new ${(event.entity ?? "records").replace("_", " ")} landed`;
        type = "data";
      } else {
        return;
      }

      setToasts((prev) => [...prev.slice(-4), { id: ++_toastId, message: msg, type }]);
    },
    [triggerPulse]
  );

  const { status } = useServerEvents(handleEvent);

  const label =
    status === "connected" ? "Live" :
    status === "connecting" ? "Connecting…" :
    "Offline";

  const labelColor =
    status === "connected" ? "#22C55E" :
    status === "connecting" ? "#F59E0B" :
    "#6B7280";

  return (
    <>
      <style>{`
        @keyframes ripple {
          0%   { transform: scale(1); opacity: 0.6; }
          100% { transform: scale(3); opacity: 0; }
        }
        @keyframes slideIn {
          from { transform: translateX(40px); opacity: 0; }
          to   { transform: translateX(0);   opacity: 1; }
        }
      `}</style>

      <span
        className="inline-flex items-center"
        style={{
          gap: 6,
          fontSize: 11,
          fontWeight: 500,
          padding: "3px 10px",
          borderRadius: 20,
          backgroundColor: status === "connected" ? "#052e16" : "#111827",
          border: `1px solid ${status === "connected" ? "#166534" : "#374151"}`,
          color: labelColor,
          transition: "all 300ms ease",
        }}
        title={status === "connected" ? "Real-time events active" : "Reconnecting…"}
      >
        <StatusDot status={status} pulsing={pulsing} />
        {label}
      </span>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
