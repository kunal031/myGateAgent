"use client";

import React, { useEffect, useRef, useState } from "react";
import { Loader2, Send, X } from "lucide-react";

import MathText from "@/components/MathText";
import {
  AssistantLanguage, AssistantMessage, askAssistant, fetchThread,
} from "@/lib/api";

interface Props {
  threadId: number;
  language: AssistantLanguage;
  onClose: () => void;
}

/** A conversation, opened from the assistant bar or a card's Explain. */
export default function ChatPanel({ threadId, language, onClose }: Props) {
  const [title, setTitle] = useState("");
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    fetchThread(threadId)
      .then((thread) => {
        if (cancelled) return;
        setTitle(thread.title);
        setMessages(thread.messages);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [threadId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const send = async (event: React.FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;

    setBusy(true);
    setDraft("");
    try {
      await askAssistant({ query: text, thread_id: threadId, language });
      const refreshed = await fetchThread(threadId);
      setMessages(refreshed.messages);
    } catch {
      // The thread is reloaded on the next send; a transient failure does
      // not need its own banner here.
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      className="flex max-h-[70vh] flex-col overflow-hidden rounded-[var(--radius-lg)]"
      style={{
        background: "var(--surface)",
        border: "var(--line-width) solid var(--line)",
        boxShadow: "var(--shadow)",
      }}
    >
      <header
        className="flex items-center justify-between gap-2 px-4 py-2.5"
        style={{ borderBottom: "var(--line-width) solid var(--line)" }}
      >
        <h2 className="min-w-0 truncate text-xs font-extrabold" style={{ color: "var(--ink)" }}>
          {title || "Conversation"}
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close conversation"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-pill)]"
          style={{ border: "var(--line-width) solid var(--line)", color: "var(--ink)" }}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {messages.map((message) => (
          <article
            key={message.id}
            className="rounded-[var(--radius)] px-3 py-2.5"
            style={{
              background: message.role === "user"
                ? "var(--accent)" : "var(--surface-muted)",
              border: "var(--line-width) solid var(--line)",
            }}
          >
            <p className="mb-1 text-[10px] font-extrabold uppercase tracking-wider"
               style={{ color: "var(--ink-faint)" }}>
              {message.role === "user" ? "You" : "Tutor"}
            </p>
            <div className="overflow-x-auto text-[13px] leading-relaxed"
                 style={{ color: "var(--ink)" }}>
              <MathText text={message.content} />
            </div>
            {message.citations.length > 0 && (
              <ul className="mt-2 space-y-0.5">
                {message.citations.slice(0, 3).map((citation, i) => (
                  <li key={i} className="truncate text-[10px] font-semibold"
                      style={{ color: "var(--ink-faint)" }}>
                    {citation}
                  </li>
                ))}
              </ul>
            )}
          </article>
        ))}

        {busy && (
          <p className="flex items-center gap-2 text-[11px] font-semibold"
             style={{ color: "var(--ink-faint)" }}>
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Thinking…
          </p>
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={send}
        className="flex items-center gap-2 px-3 py-2.5"
        style={{ borderTop: "var(--line-width) solid var(--line)" }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask a follow-up…"
          aria-label="Follow-up question"
          className="min-h-11 min-w-0 flex-1 rounded-[var(--radius-pill)] px-3.5 text-sm outline-none"
          style={{
            background: "var(--surface-sunk)",
            border: "var(--line-width) solid var(--line)",
            color: "var(--ink)",
          }}
        />
        <button
          type="submit"
          disabled={busy || !draft.trim()}
          aria-label="Send"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[var(--radius-pill)] disabled:opacity-40"
          style={{
            background: "var(--accent)",
            border: "var(--line-width) solid var(--line)",
            color: "var(--ink)",
          }}
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </section>
  );
}
