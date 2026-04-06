import { useState, useRef, useEffect, useCallback } from "react";
import { MessageSquare, X, Send, Bot, User, Loader2 } from "lucide-react";
import clsx from "clsx";
import { api } from "../api/client";
import type { AnalystMessage } from "../api/client";

export default function AskAiDrawer() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<AnalystMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, scrollToBottom]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const sendMessage = async (text?: string) => {
    const content = (text || input).trim();
    if (!content || loading) return;
    setInput("");

    const userMsg: AnalystMessage = { role: "user", content };
    const updated = [...messages, userMsg];
    setMessages(updated);
    setLoading(true);

    try {
      const res = await api.analystChat(updated);
      setMessages([...updated, { role: "assistant", content: res.reply }]);
    } catch {
      setMessages([
        ...updated,
        { role: "assistant", content: "Sorry, I couldn't generate a response. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {/* Floating button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-full bg-[#0f172a] px-4 py-3 text-white shadow-lg shadow-slate-900/20 hover:bg-slate-800 transition-colors"
        >
          <MessageSquare className="h-4 w-4" strokeWidth={2.5} />
          <span className="text-sm font-medium">Ask AI</span>
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
        </button>
      )}

      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Drawer panel */}
      <div
        className={clsx(
          "fixed top-0 right-0 z-50 h-full w-[380px] max-w-[90vw] bg-white shadow-2xl",
          "flex flex-col transition-transform duration-300 ease-in-out",
          open ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-[#0f172a]">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-gradient-to-br from-violet-500 to-brand-500">
              <Bot className="h-3 w-3 text-white" strokeWidth={2.5} />
            </div>
            <span className="text-sm font-medium text-white">AI Analyst</span>
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          </div>
          <button
            onClick={() => setOpen(false)}
            className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
          {messages.length === 0 && !loading && (
            <div className="text-center py-8">
              <Bot className="h-8 w-8 text-slate-200 mx-auto mb-3" />
              <p className="text-sm text-slate-400">Ask about your market data</p>
              <div className="mt-4 space-y-2">
                {["Top opportunities?", "Brand with worst sentiment?", "Listing price overview"].map(
                  (q) => (
                    <button
                      key={q}
                      onClick={() => sendMessage(q)}
                      className="block w-full text-left px-3 py-2 text-xs text-slate-600 rounded-lg border border-slate-100 hover:border-brand-200 hover:bg-brand-50/50 transition-colors"
                    >
                      {q}
                    </button>
                  )
                )}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={clsx("flex gap-2", msg.role === "user" ? "justify-end" : "justify-start")}
            >
              {msg.role === "assistant" && (
                <div className="flex-shrink-0 h-5 w-5 rounded bg-gradient-to-br from-violet-500 to-brand-500 flex items-center justify-center mt-0.5">
                  <Bot className="h-2.5 w-2.5 text-white" strokeWidth={2.5} />
                </div>
              )}
              <div
                className={clsx(
                  "rounded-xl px-3 py-2 max-w-[85%] text-xs leading-relaxed",
                  msg.role === "user"
                    ? "bg-brand-500 text-white rounded-br-sm"
                    : "bg-slate-50 border border-slate-100 text-slate-700 rounded-bl-sm"
                )}
              >
                {msg.content}
              </div>
              {msg.role === "user" && (
                <div className="flex-shrink-0 h-5 w-5 rounded bg-slate-200 flex items-center justify-center mt-0.5">
                  <User className="h-2.5 w-2.5 text-slate-600" strokeWidth={2.5} />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-2">
              <div className="flex-shrink-0 h-5 w-5 rounded bg-gradient-to-br from-violet-500 to-brand-500 flex items-center justify-center mt-0.5">
                <Bot className="h-2.5 w-2.5 text-white" strokeWidth={2.5} />
              </div>
              <div className="bg-slate-50 border border-slate-100 rounded-xl rounded-bl-sm px-3 py-2">
                <div className="flex items-center gap-1">
                  <div className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-pulse" />
                  <div className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-pulse" style={{ animationDelay: "0.2s" }} />
                  <div className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-pulse" style={{ animationDelay: "0.4s" }} />
                </div>
              </div>
            </div>
          )}

          <div ref={endRef} />
        </div>

        {/* Input */}
        <div className="border-t border-slate-100 px-4 py-3">
          <div className="flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question..."
              rows={1}
              className="flex-1 resize-none rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-brand-400/50 transition-colors"
              style={{ maxHeight: 80 }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = Math.min(el.scrollHeight, 80) + "px";
              }}
            />
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading}
              className={clsx(
                "flex-shrink-0 h-8 w-8 rounded-lg flex items-center justify-center transition-colors",
                input.trim() && !loading
                  ? "bg-brand-500 text-white hover:bg-brand-600"
                  : "bg-slate-100 text-slate-400"
              )}
            >
              {loading ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Send className="h-3 w-3" strokeWidth={2.5} />
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
