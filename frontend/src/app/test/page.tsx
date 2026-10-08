"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { 
  Award, 
  Settings2, 
  Play, 
  Layers, 
  Timer,
  Zap
} from "lucide-react";
import { fetchSyllabus, SubjectItem } from "@/lib/api";

export default function TestPage() {
  const [subjects, setSubjects] = useState<SubjectItem[]>([]);
  const [selectedMode, setSelectedMode] = useState<"full" | "subject" | "custom">("full");
  
  const [customSubject, setCustomSubject] = useState<string>("all");
  const [questionCount, setQuestionCount] = useState<number>(20);
  const [durationMinutes, setDurationMinutes] = useState<number>(45);

  useEffect(() => {
    fetchSyllabus().then(setSubjects).catch(console.error);
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-violet-600/20 border border-violet-500/30 flex items-center justify-center text-cyan-400">
            <Timer className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tight text-white flex items-center gap-2">
              Mock Test Engine
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-violet-500/20 text-cyan-300 border border-violet-500/30">
                100 Marks
              </span>
            </h1>
          </div>
        </div>

        <div className="text-[11px] font-mono font-bold text-slate-300 bg-[#0d1322] px-3 py-1.5 rounded-xl border border-slate-800">
          MCQ: <span className="text-rose-400">-0.33/-0.66</span> · MSQ/NAT: <span className="text-emerald-400">0 -ve</span>
        </div>
      </div>

      {/* Mode Select Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Full Mock */}
        <div
          onClick={() => setSelectedMode("full")}
          className={`p-4 rounded-xl border cursor-pointer transition-all ${
            selectedMode === "full"
              ? "bg-[#11172a] border-cyan-400 shadow-md shadow-cyan-400/10 ring-1 ring-cyan-400/40"
              : "bg-[#0d1322]/85 border-slate-800 hover:border-slate-700"
          }`}
        >
          <div className="flex items-center justify-between mb-2">
            <Award className="w-5 h-5 text-cyan-400" />
            <span className="text-[10px] font-mono font-bold text-slate-400">180 MINS</span>
          </div>
          <h3 className="font-extrabold text-sm text-white">Full Exam Mock</h3>
          <p className="text-xs text-slate-400 font-mono mt-0.5">65 Qs · 100 Marks</p>
        </div>

        {/* Subject Sprint */}
        <div
          onClick={() => setSelectedMode("subject")}
          className={`p-4 rounded-xl border cursor-pointer transition-all ${
            selectedMode === "subject"
              ? "bg-[#11172a] border-cyan-400 shadow-md shadow-cyan-400/10 ring-1 ring-cyan-400/40"
              : "bg-[#0d1322]/85 border-slate-800 hover:border-slate-700"
          }`}
        >
          <div className="flex items-center justify-between mb-2">
            <Layers className="w-5 h-5 text-violet-400" />
            <span className="text-[10px] font-mono font-bold text-slate-400">45 MINS</span>
          </div>
          <h3 className="font-extrabold text-sm text-white">Subject Sprint</h3>
          <p className="text-xs text-slate-400 font-mono mt-0.5">Single Subject Drill</p>
        </div>

        {/* Custom Mix */}
        <div
          onClick={() => setSelectedMode("custom")}
          className={`p-4 rounded-xl border cursor-pointer transition-all ${
            selectedMode === "custom"
              ? "bg-[#11172a] border-cyan-400 shadow-md shadow-cyan-400/10 ring-1 ring-cyan-400/40"
              : "bg-[#0d1322]/85 border-slate-800 hover:border-slate-700"
          }`}
        >
          <div className="flex items-center justify-between mb-2">
            <Settings2 className="w-5 h-5 text-amber-400" />
            <span className="text-[10px] font-mono font-bold text-slate-400">CUSTOM</span>
          </div>
          <h3 className="font-extrabold text-sm text-white">Custom Drill</h3>
          <p className="text-xs text-slate-400 font-mono mt-0.5">Flexible Qs & Timer</p>
        </div>
      </div>

      {/* Config Bar */}
      <div className="p-4 rounded-xl bg-[#0d1322]/85 border border-slate-800 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="space-y-1">
            <label className="text-[10px] font-mono font-bold text-slate-400 uppercase">
              Subject
            </label>
            <select
              disabled={selectedMode === "full"}
              value={customSubject}
              onChange={(e) => setCustomSubject(e.target.value)}
              className="w-full bg-[#090d16] border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:outline-none focus:border-cyan-400 disabled:opacity-50"
            >
              {selectedMode === "full" ? (
                <option value="all">All 12 Subjects</option>
              ) : (
                <>
                  <option value="all">All Subjects (Mixed)</option>
                  {subjects.map((sub) => (
                    <option key={sub.slug} value={sub.slug}>
                      {sub.name}
                    </option>
                  ))}
                </>
              )}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-[10px] font-mono font-bold text-slate-400 uppercase">
              Questions
            </label>
            <select
              disabled={selectedMode === "full"}
              value={selectedMode === "full" ? 65 : questionCount}
              onChange={(e) => setQuestionCount(Number(e.target.value))}
              className="w-full bg-[#090d16] border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:outline-none focus:border-cyan-400 disabled:opacity-50"
            >
              {selectedMode === "full" ? (
                <option value={65}>65 Questions</option>
              ) : (
                <>
                  <option value={10}>10 Questions</option>
                  <option value={20}>20 Questions</option>
                  <option value={30}>30 Questions</option>
                  <option value={50}>50 Questions</option>
                </>
              )}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-[10px] font-mono font-bold text-slate-400 uppercase">
              Time
            </label>
            <select
              disabled={selectedMode === "full"}
              value={selectedMode === "full" ? 180 : durationMinutes}
              onChange={(e) => setDurationMinutes(Number(e.target.value))}
              className="w-full bg-[#090d16] border border-slate-700 text-slate-200 text-xs rounded-lg p-2.5 focus:outline-none focus:border-cyan-400 disabled:opacity-50"
            >
              {selectedMode === "full" ? (
                <option value={180}>180 Minutes (3 Hours)</option>
              ) : (
                <>
                  <option value={20}>20 Minutes</option>
                  <option value={45}>45 Minutes</option>
                  <option value={60}>60 Minutes</option>
                  <option value={90}>90 Minutes</option>
                </>
              )}
            </select>
          </div>
        </div>

        <div className="flex justify-end pt-2 border-t border-slate-800">
          <Link
            href={`/quiz?subject=${customSubject}&limit=${selectedMode === "full" ? 65 : questionCount}`}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-bold text-xs transition shadow-md shadow-violet-600/25"
          >
            <Play className="w-3.5 h-3.5 fill-white" />
            Launch Test
          </Link>
        </div>
      </div>
    </div>
  );
}
