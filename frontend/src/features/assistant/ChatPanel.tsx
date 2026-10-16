"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Send, X } from "lucide-react";

import MathText from "@/components/MathText";
import {
  AssistantLanguage, AssistantMessage, FeedCardItem, askAssistant, fetchThread,
} from "@/lib/api";

interface Props {
  /** Null while the first answer for `card` is still being fetched. */
  threadId: number | null;
  language: AssistantLanguage;
  onClose: () => void;
  /** The card Explain was pressed on, shown while the answer is pending. */
  card?: FeedCardItem | null;
  /** True while the opening explanation is in flight. */
  pending?: boolean;
}

/**
 * A conversation over the feed, opened from the assistant bar or a card's
 * Explain button.
 *
 * It is a modal rather than a panel in the page because an explanation is a
 * detour: the feed stays where it was, and closing returns to the same
 * scroll position. Rendering it inline pushed the feed down and lost the
 * card the student was reading.
 */
export default function ChatPanel({
  threadId, language, onClose, card = null, pending = false,
}: Props) {
  const [title, setTitle] = useState("");
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (threadId === null) return;
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
  }, [messages.length, pending]);

  // Escape closes, and focus moves into the dialog so the keyboard is not
  // left behind on the feed underneath.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    inputRef.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  // The page behind must not scroll while the modal is open.
  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, []);

  const send = useCallback(async (event: React.FormEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || busy || threadId === null) return;

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
  }, [draft, busy, threadId, language]);

  const thinking = pending || busy;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4"
      style={{ background: "rgba(0,0,0,0.45)" }}
      onMouseDown={(e) => {
        // Only a click on the backdrop itself closes, not one that started
        // inside the dialog and drifted out while selecting text.
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={card ? `Explanation of ${card.title}` : "Conversation"}
        className="flex max-h-[88vh] w-full max-w-2xl flex-col overflow-hidden rounded-t-[var(--radius-lg)] sm:max-h-[82vh] sm:rounded-[var(--radius-lg)]"
        style={{
          background: "var(--surface)",
          border: "var(--line-width) solid var(--line)",
          boxShadow: "var(--shadow)",
        }}
      >
        <header
          className="flex shrink-0 items-center justify-between gap-2 px-4 py-3"
          style={{ borderBottom: "var(--line-width) solid var(--line)" }}
        >
          <div className="min-w-0">
            <p className="text-[10px] font-extrabold uppercase tracking-wider"
               style={{ color: "var(--ink-faint)" }}>
              {card ? card.subject_name : "Tutor"}
            </p>
            <h2 className="min-w-0 truncate text-sm font-extrabold"
                style={{ color: "var(--ink)" }}>
              {card ? card.title : title || "Conversation"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close explanation"
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius-pill)]"
            style={{
              background: "var(--surface-sunk)",
              border: "var(--line-width) solid var(--line)",
              color: "var(--ink)",
            }}
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
          {/* Shown while the first answer is still coming, so the modal has
              the card's own content in it from the moment it opens. */}
          {card && messages.length === 0 && (
            <article
              className="rounded-[var(--radius)] px-3 py-2.5"
              style={{
                background: "var(--surface-muted)",
                border: "var(--line-width) solid var(--line)",
              }}
            >
              <p className="mb-1 text-[10px] font-extrabold uppercase tracking-wider"
                 style={{ color: "var(--ink-faint)" }}>
                The card
              </p>
              <div className="overflow-x-auto text-[13px] leading-relaxed"
                   style={{ color: "var(--ink)" }}>
                <MathText text={card.content} />
              </div>
            </article>
          )}

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
                  {message.citations.slice(0, 4).map((citation, i) => (
                    <li key={i} className="truncate text-[10px] font-semibold"
                        style={{ color: "var(--ink-faint)" }}>
                      {citation}
                    </li>
                  ))}
                </ul>
              )}
            </article>
          ))}

          {thinking && (
            <p className="flex items-center gap-2 text-[11px] font-semibold"
               style={{ color: "var(--ink-faint)" }}>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {pending ? "Working through it…" : "Thinking…"}
            </p>
          )}
          <div ref={endRef} />
        </div>

        <form
          onSubmit={send}
          className="flex shrink-0 items-center gap-2 px-3 py-2.5"
          style={{ borderTop: "var(--line-width) solid var(--line)" }}
        >
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={card ? "Ask anything about this…" : "Ask a follow-up…"}
            aria-label="Ask a question"
            className="min-h-11 min-w-0 flex-1 rounded-[var(--radius-pill)] px-3.5 text-sm outline-none"
            style={{
              background: "var(--surface-sunk)",
              border: "var(--line-width) solid var(--line)",
              color: "var(--ink)",
            }}
          />
          <button
            type="submit"
            disabled={busy || !draft.trim() || threadId === null}
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
      </div>
    </div>
  );
}
