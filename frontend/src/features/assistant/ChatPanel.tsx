"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Loader2, Send, X } from "lucide-react";

import MathText from "@/components/MathText";
import {
  AssistantLanguage, AssistantMessage, FeedCardItem, askAndWait, fetchThread,
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
/** A spinner with elapsed seconds, shown while an answer generates.
 *
 *  The count is the point: generation runs 20-60s once Gemini's quota is
 *  exhausted and the request falls back to the second provider, and a
 *  spinner with no progress at all reads as a hung page. */
function PendingAnswer() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setSeconds((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <p className="flex items-center gap-2 text-[13px] font-semibold"
       style={{ color: "var(--ink-faint)" }}>
      <Loader2 className="h-3.5 w-3.5 animate-spin" />
      Writing an answer{seconds > 2 ? ` \u00b7 ${seconds}s` : ""}
    </p>
  );
}


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

  // Polls while anything is pending. /api/assistant/ask returns as soon
  // as the placeholder row exists and the answer is written by a
  // background job, so a single fetch showed an empty assistant bubble
  // that only filled in on a manual reload. Generation has been measured
  // at 20-60s once the Gemini quota is exhausted and the request falls
  // back to the second provider.
  useEffect(() => {
    if (threadId === null) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const load = async () => {
      try {
        const thread = await fetchThread(threadId);
        if (cancelled) return;
        setTitle(thread.title);
        setMessages(thread.messages);
        if (thread.messages.some((m) => m.status === "pending")) {
          // 2s: fast enough to feel live, slow enough that a long
          // generation is not hundreds of requests.
          timer = setTimeout(load, 2000);
        }
      } catch {
        // A dropped poll is not worth surfacing; the next one recovers.
        if (!cancelled) timer = setTimeout(load, 4000);
      }
    };
    void load();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
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
      // Refreshed as soon as the placeholder exists, so the question
      // appears immediately and the thinking state has something to sit
      // under. Without this the panel looks frozen for however long
      // generation takes -- minutes, when the key is rate limited.
      await askAndWait(
        { query: text, thread_id: threadId, language },
        {
          onPending: () => {
            void fetchThread(threadId).then((t) => setMessages(t.messages));
          },
        },
      );
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
              {message.status === "pending" ? (
                // A pending assistant row has empty content, so without
                // this the bubble was blank with no sign anything was
                // happening. The elapsed seconds matter because
                // generation can take a minute on the fallback provider
                // -- a bare spinner reads as stuck.
                <PendingAnswer />
              ) : message.status === "failed" ? (
                <p className="text-[13px] font-semibold"
                   style={{ color: "var(--danger-ink, var(--ink))" }}>
                  {message.error || "That answer could not be generated."}
                </p>
              ) : (
                <div className="overflow-x-auto text-[13px] leading-relaxed"
                     style={{ color: "var(--ink)" }}>
                  <MathText text={message.content} />
                </div>
              )}
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
