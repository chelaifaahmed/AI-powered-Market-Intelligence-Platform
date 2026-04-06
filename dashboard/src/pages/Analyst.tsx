import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Bot, User, Loader2, Sparkles, RotateCcw } from "lucide-react";
import clsx from "clsx";
import { api } from "../api/client";
import type { AnalystMessage } from "../api/client";

// ---------------------------------------------------------------------------
// CSS injected once on mount
// ---------------------------------------------------------------------------

const STYLE_ID = "analyst-styles";

const CUSTOM_CSS = `
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&display=swap');

@keyframes analyst-grid-move {
  0% { background-position: 0 0; }
  100% { background-position: 60px 60px; }
}

@keyframes analyst-fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes analyst-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

.analyst-hero-grid {
  background-image:
    linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px);
  background-size: 60px 60px;
  animation: analyst-grid-move 20s linear infinite;
}

.analyst-msg-enter {
  animation: analyst-fade-in 400ms ease-out both;
}

.analyst-typing-dot {
  animation: analyst-pulse 1.2s ease-in-out infinite;
}
.analyst-typing-dot:nth-child(2) { animation-delay: 0.2s; }
.analyst-typing-dot:nth-child(3) { animation-delay: 0.4s; }

.font-dm { font-family: 'DM Sans', sans-serif; }
`;

function useInjectStyles() {
  useEffect(() => {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = CUSTOM_CSS;
    document.head.appendChild(style);
    return () => {
      const el = document.getElementById(STYLE_ID);
      if (el) el.remove();
    };
  }, []);
}

// ---------------------------------------------------------------------------
// Markdown-lite renderer (bold, bullets, code)
// ---------------------------------------------------------------------------

function renderMarkdown(text: string) {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];

  lines.forEach((line, i) => {
    // Bold
    let processed: React.ReactNode = line;
    const boldParts = line.split(/\*\*(.*?)\*\*/g);
    if (boldParts.length > 1) {
      processed = boldParts.map((part, j) =>
        j % 2 === 1 ? <strong key={j} className="font-semibold">{part}</strong> : part
      );
    }

    // Bullet points
    if (line.match(/^[\s]*[-*]\s/)) {
      elements.push(
        <div key={i} className="flex gap-2 ml-2">
          <span className="text-brand-400 mt-0.5">&#8226;</span>
          <span>{processed}</span>
        </div>
      );
    } else if (line.match(/^```/)) {
      // skip code fences
    } else if (line.trim() === "") {
      elements.push(<div key={i} className="h-2" />);
    } else {
      elements.push(<p key={i}>{processed}</p>);
    }
  });

  return <div className="space-y-1">{elements}</div>;
}

// ---------------------------------------------------------------------------
// Suggested prompts
// ---------------------------------------------------------------------------

const SUGGESTED_PROMPTS = [
  "What are the top opportunity signals right now?",
  "Which brand has the best customer sentiment?",
  "Summarize the Tunisian insurance market",
  "What are the most common complaint types?",
  "Give me a pricing overview of car listings",
  "What articles are trending in the market?",
];

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function Analyst() {
  useInjectStyles();

  const [messages, setMessages] = useState<AnalystMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [contextUsed, setContextUsed] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, scrollToBottom]);

  const sendMessage = async (text?: string) => {
    const content = (text || input).trim();
    if (!content || loading) return;

    setInput("");
    setError(null);

    const userMsg: AnalystMessage = { role: "user", content };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setLoading(true);

    try {
      const response = await api.analystChat(updatedMessages);
      const assistantMsg: AnalystMessage = {
        role: "assistant",
        content: response.reply,
      };
      setMessages([...updatedMessages, assistantMsg]);
      setContextUsed(response.context_used);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to get response";
      setError(msg);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const resetChat = () => {
    setMessages([]);
    setError(null);
    setContextUsed([]);
    setInput("");
  };

  const hasMessages = messages.length > 0;

  return (
    <div className="flex flex-col -m-8" style={{ height: "calc(100vh - 73px)" }}>
      {/* Dark hero header */}
      <div className="relative overflow-hidden bg-[#0f172a] flex-shrink-0" style={{ minHeight: hasMessages ? 80 : 180 }}>
        <div className="absolute inset-0 analyst-hero-grid" />
        <div
          className="relative z-10 px-8 py-6 flex items-center justify-between"
          style={{ minHeight: hasMessages ? 80 : 180 }}
        >
          <div className={clsx("flex flex-col justify-center", !hasMessages && "items-center w-full text-center")}>
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-brand-500 shadow-lg shadow-violet-500/20">
                <Sparkles className="h-4.5 w-4.5 text-white" strokeWidth={2} />
              </div>
              <h1 className="font-dm text-2xl font-light text-white tracking-tight">
                AI Market Analyst
              </h1>
            </div>
            <p className="font-dm text-sm font-light text-slate-400 mt-2 max-w-lg">
              {hasMessages
                ? `${contextUsed.length} data sources active`
                : "Ask questions about your market data. Powered by Claude AI with live database context."}
            </p>
          </div>
          {hasMessages && (
            <button
              onClick={resetChat}
              className="flex items-center gap-2 rounded-lg border border-white/20 bg-transparent px-3 py-2 text-xs font-medium text-white hover:bg-white/10 transition-colors"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              New chat
            </button>
          )}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {!hasMessages && !loading ? (
          /* Empty state — suggested prompts */
          <div className="max-w-2xl mx-auto mt-4">
            <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-4">
              Try asking
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => sendMessage(prompt)}
                  className="text-left p-4 rounded-xl border border-slate-200/80 bg-white hover:border-brand-300 hover:shadow-md transition-all duration-150 group"
                >
                  <p className="text-sm text-slate-700 group-hover:text-brand-600 transition-colors">
                    {prompt}
                  </p>
                </button>
              ))}
            </div>

            {/* Context badges */}
            <div className="mt-8 flex flex-wrap gap-2 justify-center">
              {["Brands", "Reviews", "Listings", "Opportunities", "Articles", "Pipeline"].map((s) => (
                <span
                  key={s}
                  className="inline-flex items-center px-2.5 py-1 rounded-full bg-slate-100 text-[10px] font-medium text-slate-500 uppercase tracking-wide"
                >
                  {s}
                </span>
              ))}
            </div>
            <p className="text-center text-[11px] text-slate-400 mt-3">
              Live data from all platform sources is included as context
            </p>
          </div>
        ) : (
          /* Message thread */
          <div className="max-w-3xl mx-auto space-y-4">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={clsx(
                  "analyst-msg-enter flex gap-3",
                  msg.role === "user" ? "justify-end" : "justify-start"
                )}
              >
                {msg.role === "assistant" && (
                  <div className="flex-shrink-0 h-7 w-7 rounded-lg bg-gradient-to-br from-violet-500 to-brand-500 flex items-center justify-center mt-1">
                    <Bot className="h-3.5 w-3.5 text-white" strokeWidth={2.5} />
                  </div>
                )}
                <div
                  className={clsx(
                    "rounded-2xl px-4 py-3 max-w-[80%] text-sm leading-relaxed",
                    msg.role === "user"
                      ? "bg-brand-500 text-white rounded-br-md"
                      : "bg-white border border-slate-200/80 text-slate-700 rounded-bl-md shadow-sm"
                  )}
                >
                  {msg.role === "assistant" ? renderMarkdown(msg.content) : msg.content}
                </div>
                {msg.role === "user" && (
                  <div className="flex-shrink-0 h-7 w-7 rounded-lg bg-slate-200 flex items-center justify-center mt-1">
                    <User className="h-3.5 w-3.5 text-slate-600" strokeWidth={2.5} />
                  </div>
                )}
              </div>
            ))}

            {/* Typing indicator */}
            {loading && (
              <div className="analyst-msg-enter flex gap-3">
                <div className="flex-shrink-0 h-7 w-7 rounded-lg bg-gradient-to-br from-violet-500 to-brand-500 flex items-center justify-center mt-1">
                  <Bot className="h-3.5 w-3.5 text-white" strokeWidth={2.5} />
                </div>
                <div className="bg-white border border-slate-200/80 rounded-2xl rounded-bl-md px-4 py-3 shadow-sm">
                  <div className="flex items-center gap-1.5">
                    <div className="h-2 w-2 rounded-full bg-slate-400 analyst-typing-dot" />
                    <div className="h-2 w-2 rounded-full bg-slate-400 analyst-typing-dot" />
                    <div className="h-2 w-2 rounded-full bg-slate-400 analyst-typing-dot" />
                    <span className="ml-2 text-xs text-slate-400">Analyzing data...</span>
                  </div>
                </div>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="analyst-msg-enter flex gap-3">
                <div className="flex-shrink-0 h-7 w-7 rounded-lg bg-red-100 flex items-center justify-center mt-1">
                  <Bot className="h-3.5 w-3.5 text-red-500" strokeWidth={2.5} />
                </div>
                <div className="bg-red-50 border border-red-200 rounded-2xl rounded-bl-md px-4 py-3 text-sm text-red-700 max-w-[80%]">
                  {error}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="flex-shrink-0 border-t border-slate-200 bg-white px-8 py-4">
        <div className="max-w-3xl mx-auto flex gap-3 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about brands, reviews, opportunities, pricing..."
              rows={1}
              className="w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 pr-12 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-400/50 focus:border-brand-300 transition-colors"
              style={{ maxHeight: 120 }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = Math.min(el.scrollHeight, 120) + "px";
              }}
            />
          </div>
          <button
            onClick={() => sendMessage()}
            disabled={!input.trim() || loading}
            className={clsx(
              "flex-shrink-0 h-11 w-11 rounded-xl flex items-center justify-center transition-all duration-150",
              input.trim() && !loading
                ? "bg-brand-500 text-white hover:bg-brand-600 shadow-md shadow-brand-500/20"
                : "bg-slate-100 text-slate-400 cursor-not-allowed"
            )}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" strokeWidth={2.5} />
            )}
          </button>
        </div>
        <p className="text-center text-[10px] text-slate-400 mt-2 max-w-3xl mx-auto">
          AI analyst reads live database context. Responses may not be 100% accurate.
        </p>
      </div>
    </div>
  );
}
