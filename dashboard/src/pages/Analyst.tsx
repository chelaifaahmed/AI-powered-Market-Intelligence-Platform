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
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Syne:wght@700;800&display=swap');

@keyframes analyst-float {
  0%, 100% { transform: translateY(0px) rotate(0deg); }
  50% { transform: translateY(-10px) rotate(1deg); }
}

@keyframes bubble-pop {
  0% { opacity: 0; transform: scale(0.8) translateY(20px) rotateX(20deg); }
  100% { opacity: 1; transform: scale(1) translateY(0) rotateX(0deg); }
}

.analyst-page-bg {
  background: #0f172a;
  position: relative;
}
.analyst-page-bg::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: radial-gradient(circle at top right, rgba(0, 255, 255, 0.05), transparent 40%),
                    radial-gradient(circle at bottom left, rgba(255, 0, 127, 0.05), transparent 40%);
  z-index: 0;
  pointer-events: none;
}

.glass-panel {
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
}

.glass-panel-3d {
  background: linear-gradient(135deg, rgba(255,255,255,0.1), rgba(255,255,255,0));
  backdrop-filter: blur(10px);
  border-top: 1px solid rgba(255,255,255,0.2);
  border-left: 1px solid rgba(255,255,255,0.2);
  box-shadow: 5px 5px 15px rgba(0,0,0,0.5), inset -2px -2px 10px rgba(0,0,0,0.3);
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.glass-panel-3d:hover {
  transform: translateY(-5px) scale(1.02);
  box-shadow: 10px 10px 20px rgba(0,0,0,0.6), inset -2px -2px 10px rgba(0,0,0,0.3);
  border-color: #00FFFF;
}

.msg-ai {
  background: linear-gradient(135deg, rgba(255,0,127,0.15), rgba(0,255,255,0.1));
  border: 1px solid rgba(255,0,127,0.3);
  border-radius: 20px 20px 20px 4px;
}
.msg-user {
  background: linear-gradient(135deg, rgba(198,249,31,0.2), rgba(0,0,0,0.4));
  border: 1px solid rgba(198,249,31,0.4);
  border-radius: 20px 20px 4px 20px;
}

.analyst-msg-enter {
  animation: bubble-pop 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) both;
}

.glowing-text {
  text-shadow: 0 0 10px rgba(0, 255, 255, 0.5), 0 0 20px rgba(255, 0, 127, 0.3);
}

.font-dm { font-family: 'DM Sans', sans-serif; }
.font-syne { font-family: 'Syne', sans-serif; }
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
    let processed: React.ReactNode = line;
    const boldParts = line.split(/\*\*(.*?)\*\*/g);
    if (boldParts.length > 1) {
      processed = boldParts.map((part, j) =>
        j % 2 === 1 ? <strong key={j} className="text-[#00FFFF] font-bold" style={{ textShadow: "0 0 8px rgba(0,255,255,0.4)" }}>{part}</strong> : part
      );
    }

    if (line.match(/^[\s]*[-*]\s/)) {
      elements.push(
        <div key={i} className="flex gap-3 ml-2 mt-2 items-start">
          <div className="mt-1.5 h-2 w-2 rounded-full bg-[#FF007F] shadow-[0_0_8px_#FF007F] flex-shrink-0" />
          <span className="text-white/90">{processed}</span>
        </div>
      );
    } else if (line.match(/^```/)) {
    } else if (line.trim() === "") {
      elements.push(<div key={i} className="h-3" />);
    } else {
      elements.push(<p key={i} className="mb-2 text-white/90 leading-relaxed font-dm">{processed}</p>);
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
    <div className="flex flex-col -m-8 analyst-page-bg" style={{ height: "calc(100vh - 73px)" }}>
      {/* Header */}
      <div className="relative z-10 px-8 py-6 flex items-center justify-between border-b border-white/10 glass-panel flex-shrink-0" style={{ minHeight: hasMessages ? 80 : 140 }}>
        <div className={clsx("flex flex-col justify-center", !hasMessages && "items-center w-full text-center mt-4")}>
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-[#FF007F] to-[#00FFFF] shadow-[0_0_20px_rgba(255,0,127,0.5)]" style={{ animation: "analyst-float 6s ease-in-out infinite" }}>
              <Bot className="h-6 w-6 text-white" strokeWidth={2.5} />
            </div>
            <h1 className="font-dm text-2xl font-medium text-white tracking-tight">
              AI Market Analyst
            </h1>
          </div>
          <p className="font-dm text-sm font-medium text-[#C6F91F] mt-3 tracking-widest bg-black/40 px-4 py-1.5 rounded-full border border-[#C6F91F]/30 backdrop-blur-md">
            {hasMessages
              ? `✨ ${contextUsed.length} ACTIVE STREAMS ✨`
              : "READY TO CHAT. 3D INTEL UPLINK ESTABLISHED."}
          </p>
        </div>
        {hasMessages && (
          <button
            onClick={resetChat}
            className="flex items-center gap-2 rounded-xl border border-white/20 bg-white/5 hover:bg-white/10 px-4 py-2 text-xs font-bold text-white uppercase tracking-wider backdrop-blur-md transition-all hover:scale-105"
          >
            <RotateCcw className="h-4 w-4 text-[#FF007F]" />
            REBOOT
          </button>
        )}
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-8 py-8 relative z-10 w-full" style={{ perspective: "1000px" }}>
        {!hasMessages && !loading ? (
          <div className="max-w-4xl mx-auto mt-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => sendMessage(prompt)}
                  className="text-left p-6 rounded-3xl glass-panel-3d relative group overflow-hidden"
                >
                  <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#FF007F] to-[#00FFFF] transform origin-left scale-x-0 group-hover:scale-x-100 transition-transform duration-300" />
                  <Sparkles className="h-5 w-5 text-[#C6F91F] mb-3 opacity-50 group-hover:opacity-100 transition-opacity" />
                  <p className="text-sm font-bold text-white font-dm leading-relaxed">
                    {prompt}
                  </p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto space-y-8 pb-10">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={clsx(
                  "analyst-msg-enter flex gap-4 w-full",
                  msg.role === "user" ? "flex-row-reverse" : "flex-row"
                )}
              >
                <div className={clsx(
                  "flex-shrink-0 h-10 w-10 flex items-center justify-center rounded-2xl shadow-[0_0_15px_rgba(0,0,0,0.5)]",
                  msg.role === "assistant" ? "bg-gradient-to-tr from-[#FF007F] to-[#00FFFF]" : "bg-[#C6F91F]"
                )}>
                  {msg.role === "assistant" ? (
                    <Bot className="h-5 w-5 text-white" strokeWidth={2.5} />
                  ) : (
                    <User className="h-5 w-5 text-black" strokeWidth={2.5} />
                  )}
                </div>
                <div
                  className={clsx(
                    "px-6 py-5 max-w-[80%] text-base backdrop-blur-xl shadow-2xl transition-all duration-300 hover:scale-[1.01]",
                    msg.role === "user"
                      ? "msg-user text-[#C6F91F] font-semibold"
                      : "msg-ai text-white"
                  )}
                >
                  {msg.role === "assistant" ? renderMarkdown(msg.content) : msg.content}
                </div>
              </div>
            ))}

            {loading && (
              <div className="analyst-msg-enter flex gap-4">
                <div className="flex-shrink-0 h-10 w-10 flex items-center justify-center rounded-2xl bg-gradient-to-tr from-[#FF007F] to-[#00FFFF] shadow-[0_0_15px_rgba(0,0,0,0.5)]" style={{ animation: "analyst-float 3s infinite" }}>
                  <Bot className="h-5 w-5 text-white" strokeWidth={2.5} />
                </div>
                <div className="msg-ai px-6 py-5 backdrop-blur-xl flex items-center">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-5 w-5 text-[#00FFFF] animate-spin" />
                    <span className="ml-2 text-sm font-bold uppercase tracking-wider text-[#FF007F]">Synthesis in progress...</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="relative z-10 flex-shrink-0 glass-panel border-t-0 rounded-t-[40px] px-8 py-6 mx-4 mb-4 shadow-[0_-10px_40px_rgba(0,0,0,0.3)]">
        <div className="max-w-4xl mx-auto flex gap-4 items-end">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your question..."
              rows={1}
              className="w-full resize-none rounded-3xl border border-white/20 bg-black/40 px-6 py-4 pr-16 text-base font-medium text-white placeholder:text-white/40 focus:outline-none focus:border-[#00FFFF] focus:bg-black/60 shadow-inner transition-all backdrop-blur-lg"
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
              "flex-shrink-0 h-14 w-14 rounded-2xl flex items-center justify-center transition-all duration-300",
              input.trim() && !loading
                ? "bg-gradient-to-r from-[#FF007F] to-[#00FFFF] text-white shadow-[0_0_20px_rgba(255,0,127,0.6)] hover:scale-110 hover:-rotate-12"
                : "bg-white/5 text-white/20 cursor-not-allowed border border-white/10"
            )}
          >
            {loading ? (
              <Loader2 className="h-6 w-6 animate-spin" />
            ) : (
              <Send className="h-6 w-6" strokeWidth={2.5} />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
