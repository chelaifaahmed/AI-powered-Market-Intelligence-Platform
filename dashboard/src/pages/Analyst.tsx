import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Sparkles, RotateCcw } from "lucide-react";
import clsx from "clsx";
import { api, type AnalystMessage } from "../api/client";

const STYLES = `
  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes spin3d {
    0% { transform: rotateX(0deg) rotateY(0deg); }
    100% { transform: rotateX(360deg) rotateY(360deg); }
  }
  @keyframes pulseGlow {
    0%, 100% { filter: drop-shadow(0 0 10px rgba(167,139,250,0.6)); }
    50% { filter: drop-shadow(0 0 20px rgba(167,139,250,0.9)); }
  }
  
  .chat-bg {
    background: #0B101E; /* Deep charcoal / blue-black */
    position: relative;
    height: 100vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  
  .chat-bg::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image: url(/bg_fluid.png);
    background-size: cover;
    background-position: center;
    opacity: 0.15;
    mix-blend-mode: screen;
    pointer-events: none;
    z-index: 0;
  }
  
  .chat-message-ai {
    animation: fadeUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
  }

  .chat-message-user {
    animation: fadeUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  
  .input-panel {
    background: rgba(15, 23, 42, 0.6);
    backdrop-filter: blur(24px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 32px;
    transition: all 0.3s ease;
  }
  .input-panel:focus-within {
    border-color: rgba(167, 139, 250, 0.5);
    box-shadow: 0 10px 40px rgba(0,0,0,0.5), 0 0 20px rgba(167,139,250,0.15);
  }
  
  .prompt-pill {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 20px;
    padding: 12px 20px;
    font-size: 13px;
    color: #CBD5E1;
    cursor: pointer;
    transition: all 0.3s ease;
    backdrop-filter: blur(10px);
  }
  .prompt-pill:hover {
    background: rgba(167,139,250,0.15);
    border-color: rgba(167,139,250,0.4);
    color: #fff;
    transform: translateY(-2px);
  }
  
  /* Hide scrollbar for clean look */
  .no-scrollbar::-webkit-scrollbar {
    display: none;
  }
  .no-scrollbar {
    -ms-overflow-style: none;
    scrollbar-width: none;
  }
`;

function renderMarkdown(text: string) {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];

  lines.forEach((line, i) => {
    let processed: React.ReactNode = line;
    const boldParts = line.split(/\*\*(.*?)\*\*/g);
    if (boldParts.length > 1) {
      processed = boldParts.map((part, j) =>
        j % 2 === 1 ? <strong key={j} className="text-white font-semibold">{part}</strong> : part
      );
    }

    if (line.match(/^[\s]*[-*]\s/)) {
      elements.push(
        <div key={i} className="flex gap-3 ml-2 mt-2.5 items-start">
          <div className="mt-2 h-1.5 w-1.5 rounded-full bg-[#A78BFA] flex-shrink-0" />
          <span className="text-[#CBD5E1] leading-relaxed">{processed}</span>
        </div>
      );
    } else if (line.match(/^```/)) {
      // Very basic code block visual skip
    } else if (line.trim() === "") {
      elements.push(<div key={i} className="h-4" />);
    } else {
      elements.push(<p key={i} className="text-[#CBD5E1] leading-relaxed tracking-wide text-[15px]">{processed}</p>);
    }
  });

  return <div className="space-y-1">{elements}</div>;
}

const SUGGESTED_PROMPTS = [
  "What are the top opportunity signals right now?",
  "Which brand has the best customer sentiment?",
  "Summarize the current market vibes",
  "Any new alpha drops today?",
];

export default function Analyst() {
  const [messages, setMessages] = useState<AnalystMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
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
    } catch (err) {
      setMessages([...updatedMessages, { role: "assistant", content: "Signal lost. Please try again." }]);
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

  const hasMessages = messages.length > 0;

  return (
    <div className="-m-8 -mb-12 chat-bg font-sans">
      <style>{STYLES}</style>

      {/* No header - replaced with floating Reset button */}

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto px-4 relative z-10 no-scrollbar">
        <div className="max-w-3xl mx-auto pb-40 pt-10">
          {!hasMessages && (
            <div className="flex flex-col items-center justify-center h-[60vh] mt-16 text-center" style={{ animation: "fadeUp 0.8s ease-out" }}>
              <div style={{ width: 80, height: 80, position: "relative", transformStyle: "preserve-3d", animation: "spin3d 12s linear infinite", marginBottom: 32 }}>
                {[
                  { t: "rotateY(0deg) translateZ(40px)" },
                  { t: "rotateY(90deg) translateZ(40px)" },
                  { t: "rotateY(180deg) translateZ(40px)" },
                  { t: "rotateY(270deg) translateZ(40px)" },
                  { t: "rotateX(90deg) translateZ(40px)" },
                  { t: "rotateX(-90deg) translateZ(40px)" },
                ].map((f, i) => (
                  <div key={i} style={{
                    position: "absolute", width: 80, height: 80,
                    background: "rgba(167,139,250,0.05)", border: "1px solid rgba(167,139,250,0.3)",
                    backdropFilter: "blur(4px)", transform: f.t, boxShadow: "inset 0 0 20px rgba(167,139,250,0.1)"
                  }} />
                ))}
                <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyItems: "center", justifyContent: "center" }}>
                   <Sparkles className="text-[#A78BFA]" size={32} style={{ animation: 'pulseGlow 2s infinite' }} />
                </div>
              </div>
              <h2 className="text-3xl font-bold text-white mb-6 tracking-tight">How can I help you?</h2>
              <div className="flex flex-wrap justify-center gap-3 max-w-2xl mt-2">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button key={prompt} onClick={() => sendMessage(prompt)} className="prompt-pill">
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {hasMessages && (
            <div className="space-y-10">
              {messages.map((msg, i) => (
                <div key={i} className={clsx("flex gap-6 w-full", msg.role === "user" ? "chat-message-user justify-end" : "chat-message-ai")}>
                  {msg.role === "assistant" && (
                    <div className="flex-shrink-0 mt-1">
                      <Sparkles className="text-[#A78BFA]" size={20} />
                    </div>
                  )}
                  <div className={clsx("max-w-[85%]", msg.role === "user" ? "bg-white/10 px-6 py-4 rounded-3xl rounded-tr-sm text-white text-[15px] leading-relaxed font-medium shadow-md" : "py-1")}>
                    {msg.role === "assistant" ? renderMarkdown(msg.content) : msg.content}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex gap-6 w-full chat-message-ai">
                  <div className="flex-shrink-0 mt-1">
                    <Sparkles className="text-[#A78BFA] animate-pulse" size={20} />
                  </div>
                  <div className="py-2">
                    <div className="flex gap-1.5 items-center h-4">
                      <div className="w-2 h-2 rounded-full bg-[#A78BFA] animate-bounce" style={{ animationDelay: "0ms" }} />
                      <div className="w-2 h-2 rounded-full bg-[#A78BFA] animate-bounce" style={{ animationDelay: "150ms" }} />
                      <div className="w-2 h-2 rounded-full bg-[#A78BFA] animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Input Area */}
      <div className="relative z-20 flex-shrink-0 px-4 pb-8 w-full bg-gradient-to-t from-[#0B101E] via-[#0B101E]/90 to-transparent pt-6">
        <div className="max-w-3xl mx-auto">
          <div className="input-panel flex items-end p-2 pl-6">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask AI Analyste..."
              rows={1}
              className="flex-1 bg-transparent border-none text-white placeholder-[#64748B] text-[15px] resize-none focus:outline-none py-3"
              style={{ maxHeight: 150 }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = Math.min(el.scrollHeight, 150) + "px";
              }}
            />
            {hasMessages && (
              <button
                onClick={() => setMessages([])}
                className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-all text-[#94A3B8] hover:text-white hover:bg-white/5 ml-1 mb-1"
                title="Reset Chat"
              >
                <RotateCcw size={16} />
              </button>
            )}
            <button
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading}
              className={clsx(
                "flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center transition-all ml-3 mb-1",
                input.trim() && !loading
                  ? "bg-white text-black hover:scale-105"
                  : "bg-white/10 text-white/30 cursor-not-allowed"
              )}
            >
              <Send size={16} strokeWidth={2.5} className={input.trim() && !loading ? "ml-0.5" : ""} />
            </button>
          </div>
          <p className="text-center text-[11px] text-[#64748B] mt-4 font-medium tracking-wide">
            AI Analyste ✨ can make mistakes. Verify important signals.
          </p>
        </div>
      </div>
    </div>
  );
}
