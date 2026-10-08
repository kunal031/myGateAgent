"use client";

import React, { useEffect, useState } from "react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { 
  Flame, 
  AlertTriangle, 
  Binary, 
  Lightbulb, 
  Zap, 
  ArrowRight,
  Filter,
  CheckCircle2,
  RefreshCw
} from "lucide-react";
import MathText from "@/components/MathText";
import { fetchFeed, fetchSyllabus, FeedCardItem, SubjectItem } from "@/lib/api";

const TYPE_CONFIG: Record<
  string,
  { label: string; icon: LucideIcon; color: string; badgeBg: string; border: string }
> = {
  TRAP: {
    label: "TRAP ALERT",
    icon: AlertTriangle,
    color: "text-amber-400",
    badgeBg: "bg-amber-500/15 text-amber-300",
    border: "border-amber-500/40",
  },
  FORMULA: {
    label: "FORMULA",
    icon: Binary,
    color: "text-cyan-400",
    badgeBg: "bg-cyan-500/15 text-cyan-300",
    border: "border-cyan-500/40",
  },
  CONCEPT: {
    label: "CORE",
    icon: Lightbulb,
    color: "text-violet-400",
    badgeBg: "bg-violet-500/15 text-violet-300",
    border: "border-violet-500/40",
  },
  SHORTCUT: {
    label: "SHORTCUT",
    icon: Zap,
    color: "text-emerald-400",
    badgeBg: "bg-emerald-500/15 text-emerald-300",
    border: "border-emerald-500/40",
  },
};

export default function FeedPage() {
  const [cards, setCards] = useState<FeedCardItem[]>([]);
  const [subjects, setSubjects] = useState<SubjectItem[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string>("all");
  const [selectedType, setSelectedType] = useState<string>("all");
  const [loading, setLoading] = useState<boolean>(true);
  const [masteredIds, setMasteredIds] = useState<Set<number>>(new Set());
  const [reloadKey, setReloadKey] = useState<number>(0);

  // See the note in app/quiz/page.tsx: the effect owns the async flow and
  // `cancelled` guards against out-of-order responses.
  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [feedData, syllabusData] = await Promise.all([
          fetchFeed(selectedSubject, selectedType),
          fetchSyllabus(),
        ]);
        if (cancelled) return;
        setCards(feedData);
        setSubjects(syllabusData);
      } catch (err) {
        if (!cancelled) console.error("Failed to load feed", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [selectedSubject, selectedType, reloadKey]);

  const toggleMastered = (id: number) => {
    setMasteredIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Action Header */}
      <div className="flex items-center justify-between gap-3 pb-2 border-b border-slate-800/80">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-violet-600/20 border border-violet-500/30 flex items-center justify-center text-cyan-400">
            <Flame className="w-4 h-4 fill-cyan-400" />
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tight text-white flex items-center gap-2">
              Concept & Trap Feed
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-violet-500/20 text-cyan-300 border border-violet-500/30">
                {cards.length} Cards
              </span>
            </h1>
          </div>
        </div>

        <button
          onClick={() => {
            setLoading(true);
            setReloadKey((k) => k + 1);
          }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/90 hover:bg-slate-800 text-slate-300 text-xs font-semibold transition border border-slate-700/80 hover:border-violet-500/40"
        >
          <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
          Refresh
        </button>
      </div>

      {/* Filter Row */}
      <div className="p-2.5 rounded-xl bg-[#0d1322]/80 border border-slate-800/90 flex flex-wrap items-center gap-2.5">
        <Filter className="w-3.5 h-3.5 text-cyan-400 ml-1 shrink-0" />

        <select
          value={selectedSubject}
          onChange={(e) => {
            setLoading(true);
            setSelectedSubject(e.target.value);
          }}
          className="bg-[#090d16] border border-slate-700/80 text-slate-200 text-xs font-medium rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-violet-500"
        >
          <option value="all">All Subjects (12)</option>
          {subjects.map((sub) => (
            <option key={sub.slug} value={sub.slug}>
              {sub.name} (~{sub.weightage_marks}M)
            </option>
          ))}
        </select>

        <select
          value={selectedType}
          onChange={(e) => {
            setLoading(true);
            setSelectedType(e.target.value);
          }}
          className="bg-[#090d16] border border-slate-700/80 text-slate-200 text-xs font-medium rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-violet-500"
        >
          <option value="all">All Types</option>
          <option value="TRAP">Trap Alerts</option>
          <option value="FORMULA">Formulas</option>
          <option value="CONCEPT">Core Concepts</option>
          <option value="SHORTCUT">Shortcuts</option>
        </select>
      </div>

      {/* Cards List */}
      {loading ? (
        <div className="text-center py-20 text-slate-500 text-xs font-mono">
          Loading cards...
        </div>
      ) : cards.length === 0 ? (
        <div className="text-center py-16 bg-[#0d1322]/40 rounded-xl border border-slate-800 text-slate-400 text-xs font-medium">
          No cards found for this filter.
        </div>
      ) : (
        <div className="space-y-3.5">
          {cards.map((card) => {
            const typeConf = TYPE_CONFIG[card.card_type] || TYPE_CONFIG.CONCEPT;
            const IconComponent = typeConf.icon;
            const isDone = masteredIds.has(card.id);

            return (
              <div
                key={card.id}
                className={`p-4 rounded-xl border transition-all duration-200 ${
                  card.is_remedial
                    ? "bg-[#11172a] border-amber-500/50 shadow-lg shadow-amber-500/10 ring-1 ring-amber-500/30"
                    : "bg-[#0d1322]/85 border-slate-800/80 hover:border-slate-700 hover:bg-[#0f172a]/90 shadow-sm"
                } ${isDone ? "opacity-45" : ""}`}
              >
                {/* Header */}
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] font-extrabold tracking-wider border ${typeConf.badgeBg} ${typeConf.border}`}
                    >
                      <IconComponent className="w-3 h-3" />
                      {typeConf.label}
                    </span>

                    <span className="text-[11px] font-semibold text-slate-300">
                      {card.subject_name} · <span className="text-slate-400">{card.topic_name}</span>
                    </span>
                  </div>

                  {card.is_remedial && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 text-[10px] font-black border border-amber-500/40">
                      <Flame className="w-3 h-3 text-amber-400 fill-amber-400" />
                      PRIORITY: {card.recent_mistakes_in_topic} MISTAKE(S)
                    </span>
                  )}
                </div>

                {/* Title */}
                <h3 className="text-sm font-bold text-white tracking-tight mb-2">
                  {card.title}
                </h3>

                {/* Content */}
                <div className="text-xs sm:text-[13px] text-slate-200 bg-[#070a13]/90 p-3.5 rounded-lg border border-slate-800/90 mb-2.5">
                  <MathText text={card.content} />
                </div>

                {/* Golden Takeaway */}
                <div className="p-2.5 rounded-lg bg-gradient-to-r from-violet-950/40 to-slate-900 border border-violet-500/30 mb-2">
                  <div className="text-[10px] font-mono font-bold text-cyan-400 uppercase tracking-wider mb-0.5">
                    KEY TAKEAWAY:
                  </div>
                  <div className="text-xs text-white font-medium">
                    <MathText text={card.takeaway} />
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-xs">
                  <button
                    onClick={() => toggleMastered(card.id)}
                    className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-semibold transition ${
                      isDone
                        ? "text-emerald-400 bg-emerald-500/10"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/80"
                    }`}
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    {isDone ? "Mastered" : "Mark Mastered"}
                  </button>

                  <Link
                    href={`/quiz?subject=${card.subject_slug}&topic=${card.topic_slug}`}
                    className="flex items-center gap-1 text-cyan-400 hover:text-cyan-300 text-xs font-bold"
                  >
                    Drill Topic
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
