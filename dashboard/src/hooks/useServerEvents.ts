import { useEffect, useRef, useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

export type ServerEventType =
  | "connected"
  | "heartbeat"
  | "pipeline_complete"
  | "opportunity_update"
  | "data_update";

export interface ServerEvent {
  type: ServerEventType;
  // pipeline_complete
  component?: string;
  records?: number;
  status?: string;
  // opportunity_update
  strong?: number;
  moderate?: number;
  total?: number;
  top_entity?: string;
  top_score?: number;
  // data_update
  entity?: string;
  count?: number;
}

export type ConnectionStatus = "connecting" | "connected" | "disconnected";

interface UseServerEventsResult {
  status: ConnectionStatus;
  lastEvent: ServerEvent | null;
}

const RECONNECT_DELAY_MS = 5000;

export function useServerEvents(
  onEvent?: (event: ServerEvent) => void
): UseServerEventsResult {
  const queryClient = useQueryClient();
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);

  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [lastEvent, setLastEvent] = useState<ServerEvent | null>(null);

  const connect = useCallback(() => {
    if (!mounted.current) return;

    setStatus("connecting");
    const es = new EventSource("/api/events/stream");
    esRef.current = es;

    es.onmessage = (e: MessageEvent) => {
      if (!mounted.current) return;
      let event: ServerEvent;
      try {
        event = JSON.parse(e.data as string) as ServerEvent;
      } catch {
        return;
      }

      if (event.type === "connected") {
        setStatus("connected");
        return;
      }
      if (event.type === "heartbeat") return;

      setLastEvent(event);
      onEvent?.(event);

      // Invalidate all queries so every page refreshes automatically
      if (
        event.type === "pipeline_complete" ||
        event.type === "opportunity_update" ||
        event.type === "data_update"
      ) {
        void queryClient.invalidateQueries();
      }
    };

    es.onerror = () => {
      if (!mounted.current) return;
      es.close();
      esRef.current = null;
      setStatus("disconnected");
      // Auto-reconnect after delay
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };
  }, [queryClient, onEvent]);

  useEffect(() => {
    mounted.current = true;
    connect();
    return () => {
      mounted.current = false;
      esRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connect]);

  return { status, lastEvent };
}
