"use client";

import React, { useState, useEffect } from "react";
import { 
  Bot, 
  Send, 
  Sparkles, 
  BookOpen, 
  Globe, 
  Zap,
  FolderSync
} from "lucide-react";
import MathText from "@/components/MathText";
import { chatWithAgent, fetchAgentDocuments, AgentDocumentsResponse } from "@/lib/api";

interface Message {
  role: "user" | "agent";
  content: string;
  source?: string;
  excerpts?: {
    content: string;
    file_name: string;
    page_number: number;
  }[];
}

const PRESET_QUERIES = [
  "2 tricky MSQs on Virtual Memory Paging",
  "Counter-example: CFL not closed under complementation",
  "Euler planar graph formula shortcut",
  "BCNF vs 3NF dependency preservation trap",
];

export default function AgentPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "agent",
      content:
        "**AI Professor & Notes Knowledge Base Active**\\n\\nIndexed on your synced handwritten notes, standard references (Cormen, Galvin, Tanenbaum, Ullman), and 35 years GATE CSE PYQs.\\n\\nAsk any question, request variant MSQ/NAT traps, or search specific theorems from your notes.",
      source: "Knowledge Base: Synced Notes + Standard Texts",
    },
  ]);
  const [input, setInput] = useState<string>("");
  const [isThinking, setIsThinking] = useState<boolean>(false);
  const [docStats, setDocStats] = useState<AgentDocumentsResponse | null>(null);

  useEffect(() => {
    fetchAgentDocuments()
      .then(setDocStats)
      .catch((e) => console.log("Documents status check", e));
  }, []);

  const handleSend = async (text?: string) => {
    const query = text || input;
    if (!query.trim() || isThinking) return;

    const userMsg: Message = {
      role: "user",
      content: query,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsThinking(true);

    try {
      const res = await chatWithAgent(query);
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          content: res.reply,
          source: res.source,
          excerpts: res.matched_excerpts,
        },
      ]);
    } catch (err) {
      console.error("Chat error", err);
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          content: "Encountered a retrieval issue. Please verify backend connection.",
          source: "Error",
        },
      ]);
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-4rem)] flex flex-col space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800/80 shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-violet-600/20 border border-violet-500/30 flex items-center justify-center text-cyan-400">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tight text-white flex items-center gap-2">
              AI Agent & RAG
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                Live RAG
              </span>
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
          <FolderSync className="w-3.5 h-3.5 text-cyan-400" />
          <span>
            {docStats ? `${docStats.total_documents} Synced Files` : "Syncing Drive Notes"}
          </span>
        </div>
      </div>

      {/* Quick Prompts */}
      <div className="flex flex-wrap gap-1.5 shrink-0">
        {PRESET_QUERIES.map((p, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(p)}
            className="text-[11px] font-semibold px-2.5 py-1 rounded-lg bg-[#0d1322] hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white transition flex items-center gap-1.5"
          >
            <Sparkles className="w-3 h-3 text-cyan-400 shrink-0" />
            <span className="truncate max-w-xs">{p}</span>
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 bg-[#0d1322]/80 rounded-xl border border-slate-800/90 p-4 overflow-y-auto space-y-3">
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`flex flex-col ${
              m.role === "user" ? "items-end" : "items-start"
            }`}
          >
            <div
              className={`max-w-2xl p-3.5 rounded-xl text-xs sm:text-[13px] leading-relaxed ${
                m.role === "user"
                  ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white rounded-br-none shadow-md"
                  : "bg-[#070a13] border border-slate-800 text-slate-200 rounded-bl-none shadow-sm"
              }`}
            >
              <MathText text={m.content} />

              {m.source && (
                <div className="mt-2.5 pt-1.5 border-t border-slate-800/80 flex items-center gap-1.5 text-[10px] text-slate-400 font-mono">
                  <BookOpen className="w-3 h-3 text-cyan-400" />
                  <span>{m.source}</span>
                </div>
              )}
            </div>
          </div>
        ))}

        {isThinking && (
          <div className="flex items-center gap-2 text-xs text-cyan-400 font-medium py-1">
            <Zap className="w-3.5 h-3.5 animate-pulse text-cyan-400" />
            <span>Consulting your notes & RAG vector store...</span>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="shrink-0 p-2 rounded-xl bg-[#0d1322] border border-slate-800 flex items-center gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="Ask a question from your notes or request custom GATE traps..."
          className="flex-1 bg-transparent px-3 py-1.5 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
        />

        <button
          onClick={() => handleSend()}
          disabled={!input.trim() || isThinking}
          className="p-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white transition disabled:opacity-40"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
