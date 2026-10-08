"use client";

import React, { Suspense, useEffect, useState, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  Timer, 
  Filter, 
  ArrowRight, 
  Zap,
  BookOpen
} from "lucide-react";
import MathText from "@/components/MathText";
import { 
  fetchQuiz, 
  fetchSyllabus, 
  submitQuizAnswer, 
  QuizQuestion, 
  SubjectItem, 
  SubmitResponse 
} from "@/lib/api";

function QuizDrill() {
  const searchParams = useSearchParams();

  // Inbound deep links: /quiz?subject=...&topic=...&limit=...
  // Sent by the feed "Drill Topic" link, the analytics "Start" link, and the
  // test page "Launch Test" button.
  const urlSubject = searchParams.get("subject") || "all";
  const urlTopic = searchParams.get("topic") || "all";
  const urlType = searchParams.get("type") || "all";
  const urlDifficulty = searchParams.get("difficulty") || "all";
  const urlLimit = Number(searchParams.get("limit")) || 20;

  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [subjects, setSubjects] = useState<SubjectItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);

  // Filters — seeded from the URL so deep links land pre-filtered
  const [selectedSubject, setSelectedSubject] = useState<string>(urlSubject);
  const [selectedTopic, setSelectedTopic] = useState<string>(urlTopic);
  const [selectedType, setSelectedType] = useState<string>(urlType);
  const [selectedDifficulty, setSelectedDifficulty] = useState<string>(urlDifficulty);

  // Interaction State
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);
  const [natAnswer, setNatAnswer] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [result, setResult] = useState<SubmitResponse | null>(null);

  // Question Timer
  const [timeSpent, setTimeSpent] = useState<number>(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Reload whenever filters change. The effect owns the async flow so no
  // setState happens synchronously in the effect body, and `cancelled`
  // prevents a slow response for old filters from overwriting newer results.
  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [qData, sData] = await Promise.all([
          fetchQuiz({
            subject_slug: selectedSubject,
            topic_slug: selectedTopic,
            question_type: selectedType,
            difficulty: selectedDifficulty,
            limit: urlLimit,
          }),
          fetchSyllabus(),
        ]);
        if (cancelled) return;
        setQuestions(qData);
        setSubjects(sData);
        setResult(null);
        setSelectedOptions([]);
        setNatAnswer("");
        setCurrentIndex(0);
        setTimeSpent(0);
      } catch (err) {
        if (!cancelled) console.error("Failed to load quiz questions", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [selectedSubject, selectedTopic, selectedType, selectedDifficulty, urlLimit]);

  useEffect(() => {
    if (result !== null || loading || questions.length === 0) {
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }

    timerRef.current = setInterval(() => {
      setTimeSpent((prev) => prev + 1);
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [currentIndex, result, loading, questions.length]);

  const currentQ = questions[currentIndex];

  const handleOptionToggle = (optionId: string) => {
    if (result !== null) return;

    if (currentQ.question_type === "MCQ") {
      setSelectedOptions([optionId]);
    } else if (currentQ.question_type === "MSQ") {
      setSelectedOptions((prev) =>
        prev.includes(optionId)
          ? prev.filter((id) => id !== optionId)
          : [...prev, optionId].sort()
      );
    }
  };

  const handleSubmit = async () => {
    if (!currentQ || submitting) return;

    let ans = "";
    if (currentQ.question_type === "NAT") {
      if (!natAnswer.trim()) {
        alert("Enter numerical answer");
        return;
      }
      ans = natAnswer.trim();
    } else {
      if (selectedOptions.length === 0) {
        alert("Select at least one option");
        return;
      }
      ans = selectedOptions.join(",");
    }

    setSubmitting(true);
    try {
      const res = await submitQuizAnswer({
        question_id: currentQ.id,
        user_answer: ans,
        time_spent_seconds: timeSpent,
        mode: "quiz",
      });
      setResult(res);
    } catch (err) {
      console.error("Failed to submit answer", err);
      alert("Submission error.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((prev) => prev + 1);
      setSelectedOptions([]);
      setNatAnswer("");
      setResult(null);
      setTimeSpent(0);
    }
  };

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      {/* Header Bar */}
      <div className="flex items-center justify-between gap-3 pb-2 border-b border-slate-800/80">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-violet-600/20 border border-violet-500/30 flex items-center justify-center text-cyan-400">
            <Zap className="w-4 h-4 fill-cyan-400" />
          </div>
          <div>
            <h1 className="text-xl font-black tracking-tight text-white flex items-center gap-2">
              Quiz Drill
              {questions.length > 0 && (
                <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-violet-500/20 text-cyan-300 border border-violet-500/30">
                  {currentIndex + 1} / {questions.length}
                </span>
              )}
            </h1>
          </div>
        </div>

        {questions.length > 0 && (
          <div className="flex items-center gap-2 bg-[#0d1322] px-3 py-1.5 rounded-xl border border-slate-800">
            <Timer className="w-4 h-4 text-amber-400" />
            <span className="font-mono text-xs font-bold text-amber-300">
              {formatTimer(timeSpent)}
            </span>
          </div>
        )}
      </div>

      {/* Filter Row */}
      <div className="p-2.5 rounded-xl bg-[#0d1322]/80 border border-slate-800/90 flex flex-wrap items-center gap-2.5">
        <Filter className="w-3.5 h-3.5 text-cyan-400 ml-1 shrink-0" />

        <select
          value={selectedSubject}
          onChange={(e) => {
            setLoading(true);
            setSelectedSubject(e.target.value);
            setSelectedTopic("all");
          }}
          className="bg-[#090d16] border border-slate-700/80 text-slate-200 text-xs font-medium rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-violet-500"
        >
          <option value="all">All Subjects (12)</option>
          {subjects.map((sub) => (
            <option key={sub.slug} value={sub.slug}>
              {sub.name}
            </option>
          ))}
        </select>

        {selectedSubject !== "all" && (
          <select
            value={selectedTopic}
            onChange={(e) => {
              setLoading(true);
              setSelectedTopic(e.target.value);
            }}
            className="bg-[#090d16] border border-slate-700/80 text-slate-200 text-xs font-medium rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-violet-500"
          >
            <option value="all">All Topics</option>
            {subjects
              .find((s) => s.slug === selectedSubject)
              ?.topics.map((t) => (
                <option key={t.slug} value={t.slug}>
                  {t.name}
                </option>
              ))}
          </select>
        )}

        <select
          value={selectedType}
          onChange={(e) => {
            setLoading(true);
            setSelectedType(e.target.value);
          }}
          className="bg-[#090d16] border border-slate-700/80 text-slate-200 text-xs font-medium rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-violet-500"
        >
          <option value="all">All Types</option>
          <option value="MCQ">MCQ</option>
          <option value="MSQ">MSQ</option>
          <option value="NAT">NAT</option>
        </select>

        <select
          value={selectedDifficulty}
          onChange={(e) => {
            setLoading(true);
            setSelectedDifficulty(e.target.value);
          }}
          className="bg-[#090d16] border border-slate-700/80 text-slate-200 text-xs font-medium rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-violet-500"
        >
          <option value="all">All Difficulties</option>
          <option value="Foundational">Foundational</option>
          <option value="Standard GATE">Standard GATE</option>
          <option value="Rank Booster">Rank Booster</option>
        </select>
      </div>

      {/* Question Card */}
      {loading ? (
        <div className="text-center py-20 text-slate-500 text-xs font-mono">
          Loading questions...
        </div>
      ) : questions.length === 0 ? (
        <div className="text-center py-16 bg-[#0d1322]/40 rounded-xl border border-slate-800 text-slate-400 text-xs font-medium">
          No questions found for this filter.
        </div>
      ) : (
        <div className="p-5 rounded-xl bg-[#0d1322]/85 border border-slate-800 space-y-4 shadow-lg shadow-black/40">
          {/* Question Tag Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-800">
            <div className="flex items-center gap-2">
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider border ${
                  currentQ.question_type === "MCQ"
                    ? "bg-blue-500/15 text-blue-300 border-blue-500/40"
                    : currentQ.question_type === "MSQ"
                    ? "bg-purple-500/15 text-purple-300 border-purple-500/40"
                    : "bg-emerald-500/15 text-emerald-300 border-emerald-500/40"
                }`}
              >
                {currentQ.question_type}
              </span>

              <span className="text-xs font-bold text-slate-200 bg-[#090d16] px-2 py-0.5 rounded border border-slate-800">
                +{currentQ.marks}M
                {currentQ.question_type === "MCQ" && (
                  <span className="text-rose-400 ml-1">(-{currentQ.negative_marks})</span>
                )}
                {currentQ.question_type !== "MCQ" && (
                  <span className="text-slate-400 ml-1">(0 -ve)</span>
                )}
              </span>

              <span className="text-xs font-semibold text-slate-300">
                {currentQ.subject_name} · <span className="text-slate-400">{currentQ.topic_name}</span>
              </span>
            </div>

            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800/80 text-slate-400 border border-slate-700/60">
                {currentQ.difficulty}
              </span>
              {currentQ.is_pyq && (
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
                  PYQ
                </span>
              )}
            </div>
          </div>

          {/* Question Content */}
          <div className="text-slate-100 text-sm md:text-[15px] leading-relaxed bg-[#070a13]/90 p-4 rounded-xl border border-slate-800/90">
            <MathText text={currentQ.content} />
          </div>

          {/* MSQ Notice */}
          {currentQ.question_type === "MSQ" && (
            <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-purple-950/30 border border-purple-500/30 text-purple-300 text-xs font-semibold">
              <AlertCircle className="w-3.5 h-3.5 text-purple-400 shrink-0" />
              <span>MSQ: One or more options can be correct. No partial credit.</span>
            </div>
          )}

          {/* Options Interface */}
          {currentQ.question_type === "NAT" ? (
            <div className="p-4 rounded-xl bg-[#070a13]/70 border border-slate-800 flex items-center gap-3">
              <span className="text-xs font-mono font-bold text-slate-400 uppercase">Answer:</span>
              <input
                type="number"
                step="any"
                disabled={result !== null}
                value={natAnswer}
                onChange={(e) => setNatAnswer(e.target.value)}
                placeholder="Enter value"
                className="bg-[#090d16] border border-slate-700 text-slate-100 font-mono text-base px-3.5 py-2 rounded-lg w-48 focus:outline-none focus:border-cyan-400 disabled:opacity-60"
              />
            </div>
          ) : (
            <div className="space-y-2">
              {currentQ.options?.map((opt) => {
                const isSelected = selectedOptions.includes(opt.id);

                return (
                  <div
                    key={opt.id}
                    onClick={() => handleOptionToggle(opt.id)}
                    className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all duration-150 ${
                      isSelected
                        ? "bg-violet-600/20 border-cyan-400/80 text-white shadow-md shadow-violet-600/10 ring-1 ring-cyan-400/50"
                        : "bg-[#070a13]/70 border-slate-800 text-slate-300 hover:border-slate-700 hover:bg-[#090d16]"
                    } ${result !== null ? "pointer-events-none opacity-85" : ""}`}
                  >
                    <div
                      className={`w-5 h-5 rounded flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold font-mono transition ${
                        isSelected
                          ? "bg-cyan-400 text-black font-extrabold shadow-sm shadow-cyan-400/50"
                          : "border border-slate-600 text-slate-400"
                      } ${currentQ.question_type === "MCQ" ? "rounded-full" : "rounded"}`}
                    >
                      {opt.id}
                    </div>

                    <div className="flex-1 text-xs sm:text-[13px]">
                      <MathText text={opt.text} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Submit Action */}
          {result === null ? (
            <div className="flex justify-end pt-1">
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="px-5 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white text-xs font-bold transition shadow-md shadow-violet-600/25 disabled:opacity-50"
              >
                {submitting ? "Checking..." : "Submit Answer"}
              </button>
            </div>
          ) : (
            /* Result Banner */
            <div className="space-y-3 pt-3 border-t border-slate-800">
              <div
                className={`p-3.5 rounded-xl flex items-center justify-between gap-3 border ${
                  result.is_correct
                    ? "bg-emerald-950/20 border-emerald-500/40 text-emerald-200"
                    : "bg-rose-950/20 border-rose-500/40 text-rose-200"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  {result.is_correct ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                  ) : (
                    <XCircle className="w-5 h-5 text-rose-400 shrink-0" />
                  )}
                  <div className="text-xs">
                    <span className="font-bold">
                      {result.is_correct ? "Correct" : "Incorrect"}
                    </span>
                    <span className="mx-2 text-slate-500">|</span>
                    <span className="font-mono font-bold">
                      {result.marks_awarded > 0 ? `+${result.marks_awarded}` : result.marks_awarded}M
                    </span>
                    <span className="mx-2 text-slate-500">|</span>
                    <span>Key: <strong className="font-mono text-cyan-300">{result.correct_answer}</strong></span>
                  </div>
                </div>

                {currentIndex < questions.length - 1 && (
                  <button
                    onClick={handleNext}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-bold transition"
                  >
                    Next
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {/* Step-by-Step KaTeX Explanation */}
              <div className="p-4 rounded-xl bg-[#070a13] border border-slate-800/90 space-y-1.5">
                <div className="flex items-center gap-1.5 text-[11px] font-mono font-bold text-cyan-400 uppercase">
                  <BookOpen className="w-3.5 h-3.5" />
                  <span>Explanation:</span>
                </div>
                <div className="text-xs sm:text-[13px] text-slate-200 pt-1">
                  <MathText text={result.explanation} />
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function QuizPage() {
  return (
    <Suspense
      fallback={
        <div className="text-center py-20 text-slate-500 text-xs font-mono">
          Loading drill...
        </div>
      }
    >
      <QuizDrill />
    </Suspense>
  );
}
