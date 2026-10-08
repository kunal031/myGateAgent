"use client";

import React from "react";
import Link from "next/link";
import {
  AlertTriangle, ArrowRight, Binary, CheckCircle2, Flame, Lightbulb, Zap,
  type LucideIcon,
} from "lucide-react";

import MathText from "@/components/MathText";
import { FeedCardItem } from "@/lib/api";

const TYPE_CONFIG: Record<string, { label: string; icon: LucideIcon; token: string }> = {
  TRAP: { label: "TRAP ALERT", icon: AlertTriangle, token: "var(--trap)" },
  FORMULA: { label: "FORMULA", icon: Binary, token: "var(--formula)" },
  CONCEPT: { label: "CORE", icon: Lightbulb, token: "var(--concept)" },
  SHORTCUT: { label: "SHORTCUT", icon: Zap, token: "var(--shortcut)" },
};

interface Props {
  card: FeedCardItem;
  mastered: boolean;
  onToggleMastered: (id: number) => void;
}

export default function FeedCard({ card, mastered, onToggleMastered }: Props) {
  const config = TYPE_CONFIG[card.card_type] ?? TYPE_CONFIG.CONCEPT;
  const Icon = config.icon;

  return (
    <article
      className="overflow-hidden rounded-[var(--radius-lg)] transition-opacity"
      style={{
        background: "var(--surface)",
        border: "var(--line-width) solid var(--line)",
        boxShadow: card.is_remedial ? "var(--shadow)" : "var(--shadow-sm)",
        opacity: mastered ? 0.55 : 1,
      }}
    >
      <div className="flex flex-wrap items-center gap-2 px-4 pt-4">
        <span
          className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-2.5 py-1 text-[10px] font-extrabold tracking-wider"
          style={{
            background: config.token,
            color: "var(--ink)",
            border: "var(--line-width) solid var(--line)",
          }}
        >
          <Icon className="h-3 w-3" />
          {config.label}
        </span>

        {card.is_remedial && (
          <span
            className="inline-flex items-center gap-1 rounded-[var(--radius-pill)] px-2.5 py-1 text-[10px] font-extrabold"
            style={{
              background: "var(--danger)",
              color: "var(--ink)",
              border: "var(--line-width) solid var(--line)",
            }}
          >
            <Flame className="h-3 w-3" />
            {card.recent_mistakes_in_topic} MISTAKE
            {card.recent_mistakes_in_topic === 1 ? "" : "S"}
          </span>
        )}
      </div>

      <div className="px-4 pt-2">
        <p className="break-words text-[11px] font-semibold" style={{ color: "var(--ink-faint)" }}>
          {card.subject_name} · {card.topic_name}
        </p>
        <h3 className="mt-1 break-words text-base font-bold leading-snug" style={{ color: "var(--ink)" }}>
          {card.title}
        </h3>
      </div>

      {/* min-w-0 + overflow-x-auto stop wide formulas widening the page. */}
      <div className="min-w-0 px-4 py-3">
        <div
          className="overflow-x-auto rounded-[var(--radius)] px-3.5 py-3 text-[13px] leading-relaxed"
          style={{
            background: "var(--surface-muted)",
            border: "var(--line-width) solid var(--line)",
            color: "var(--ink-soft)",
          }}
        >
          <MathText text={card.content} />
        </div>
      </div>

      <div className="px-4 pb-3">
        <div
          className="overflow-x-auto rounded-[var(--radius)] px-3.5 py-2.5"
          style={{
            background: "var(--accent)",
            border: "var(--line-width) solid var(--line)",
          }}
        >
          <p className="text-[10px] font-extrabold tracking-wider" style={{ color: "var(--ink-faint)" }}>
            KEY TAKEAWAY
          </p>
          <div className="mt-0.5 text-[13px] font-medium" style={{ color: "var(--ink)" }}>
            <MathText text={card.takeaway} />
          </div>
        </div>
      </div>

      <div
        className="flex items-center justify-between gap-2 px-4 py-2.5"
        style={{ borderTop: "var(--line-width) solid var(--line)" }}
      >
        <button
          type="button"
          onClick={() => onToggleMastered(card.id)}
          className="flex min-h-11 items-center gap-1.5 rounded-[var(--radius-pill)] px-3 text-xs font-bold"
          style={{
            background: mastered ? "var(--success)" : "transparent",
            color: "var(--ink)",
            border: mastered
              ? "var(--line-width) solid var(--line)"
              : "var(--line-width) solid transparent",
          }}
        >
          <CheckCircle2 className="h-4 w-4" />
          {mastered ? "Mastered" : "Mark mastered"}
        </button>

        <Link
          href={`/quiz?subject=${card.subject_slug}&topic=${card.topic_slug}`}
          className="flex min-h-11 items-center gap-1 rounded-[var(--radius-pill)] px-3 text-xs font-bold"
          style={{ color: "var(--ink)" }}
        >
          Drill topic
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </article>
  );
}
