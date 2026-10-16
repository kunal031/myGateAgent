"use client";

import React, { useState } from "react";
import { Loader2, Search, Sparkles } from "lucide-react";

import {
  AssistantLanguage, AssistantResult, askAssistant,
} from "@/lib/api";

const LANGUAGES: { key: AssistantLanguage; label: string }[] = [
  { key: "en", label: "EN" },
  { key: "hi", label: "हिं" },
  { key: "hinglish", label: "Hinglish" },
];

interface Props {
  /** A request for cards: the feed reloads with these filters. */
  onFilters: (filters: {
    subjectSlug?: string;
    cardType?: string;
    mode?: string;
  }) => void;
  /** A question: the chat panel opens on this thread. */
  onChat: (threadId: number) => void;
  /** Lifted so Explain and follow-ups use the same language. */
  language: AssistantLanguage;
  onLanguageChange: (language: AssistantLanguage) => void;
}

/**
 * One box for both outcomes. The backend classifies the request, so asking
 * for cards refills the feed and asking a question opens a conversation --
 * the student does not have to know which mode they are in.
 */
export default function AssistantBar({
  onFilters, onChat, language, onLanguageChange,
}: Props) {
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const text = query.trim();
    if (!text || busy) return;

    setBusy(true);
    setError(null);
    try {
      const result: AssistantResult = await askAssistant({ query: text, language });
      if (result.output === "feed") {
        onFilters({
          subjectSlug: result.filters.subject_slug ?? undefined,
          cardType: result.filters.card_type ?? undefined,
          mode: result.filters.level === "foundational" ? "BASIC"
              : result.filters.level === "advanced" ? "ADVANCED"
              : undefined,
        });
      } else {
        onChat(result.thread_id);
      }
      setQuery("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assistant unavailable");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      <form onSubmit={submit} className="flex items-center gap-2">
        <div
          className="flex min-h-12 flex-1 items-center gap-2 rounded-[var(--radius-pill)] px-4"
          style={{
            background: "var(--surface)",
            border: "var(--line-width) solid var(--line)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <Search className="h-4 w-4 shrink-0" style={{ color: "var(--ink-faint)" }} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask for cards, or ask a question…"
            aria-label="Ask the assistant"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none"
            style={{ color: "var(--ink)" }}
          />
          <span
            className="hidden shrink-0 items-center gap-1 rounded-[var(--radius-pill)] px-2 py-0.5 text-[10px] font-bold sm:flex"
            style={{ background: "var(--surface-sunk)", color: "var(--ink-faint)" }}
          >
            {LANGUAGES.map((l) => (
              <button
                key={l.key}
                type="button"
                onClick={() => onLanguageChange(l.key)}
                className="rounded-[var(--radius-pill)] px-1.5 py-0.5"
                style={{
                  background: language === l.key ? "var(--accent)" : "transparent",
                  color: language === l.key ? "var(--ink)" : "var(--ink-faint)",
                }}
              >
                {l.label}
              </button>
            ))}
          </span>
        </div>

        <button
          type="submit"
          disabled={busy || !query.trim()}
          aria-label="Ask"
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-[var(--radius-pill)] disabled:opacity-40"
          style={{
            background: "var(--accent)",
            border: "var(--line-width) solid var(--line)",
            color: "var(--ink)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          {busy
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : <Sparkles className="h-4 w-4" />}
        </button>
      </form>

      {error && (
        <p className="px-3 text-[11px] font-semibold" style={{ color: "var(--ink)" }}>
          {error}
        </p>
      )}
    </div>
  );
}
