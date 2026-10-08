"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  Flame, 
  HelpCircle, 
  Bot, 
  Timer, 
  BarChart3, 
  Zap,
  Crosshair
} from "lucide-react";

const NAV_ITEMS = [
  { name: "Feed", href: "/feed", icon: Flame, tag: "Recall" },
  { name: "Quiz", href: "/quiz", icon: HelpCircle, tag: "Drill" },
  { name: "Agent + Chat", href: "/agent", icon: Bot, tag: "RAG" },
  { name: "Test", href: "/test", icon: Timer, tag: "Mock" },
  { name: "Analytics", href: "/analytics", icon: BarChart3, tag: "Stats" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-60 bg-[#090d16]/95 border-r border-slate-800/80 backdrop-blur-xl flex flex-col h-screen fixed left-0 top-0 text-slate-200 z-30 select-none">
      {/* Brand Header */}
      <div className="p-4 border-b border-slate-800/70">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-violet-600 via-indigo-600 to-cyan-400 p-[1px] shadow-lg shadow-violet-600/30">
            <div className="w-full h-full bg-[#090d16] rounded-[11px] flex items-center justify-center text-cyan-400">
              <Zap className="w-4 h-4 fill-cyan-400" />
            </div>
          </div>
          <div>
            <div className="font-extrabold text-sm tracking-wider text-white flex items-center gap-1.5">
              <span>GATEMASTER</span>
              <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-violet-500/20 text-violet-300 border border-violet-500/40">
                2027
              </span>
            </div>
            <p className="text-[10px] font-mono font-semibold text-cyan-400/90 tracking-wide">
              TARGET: 80+ MARKS
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2.5 space-y-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || (item.href === "/feed" && pathname === "/");

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center justify-between px-3 py-2.5 rounded-xl font-medium text-xs transition-all duration-200 ${
                isActive
                  ? "bg-gradient-to-r from-violet-600/25 to-cyan-500/10 text-white border border-violet-500/40 shadow-md shadow-violet-600/10 font-semibold"
                  : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/50 border border-transparent"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Icon className={`w-4 h-4 transition-colors ${
                  isActive ? "text-cyan-400" : "text-slate-400 group-hover:text-slate-200"
                }`} />
                <span>{item.name}</span>
              </div>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                isActive 
                  ? "bg-violet-500/20 text-cyan-300 border border-violet-400/30" 
                  : "bg-slate-800/60 text-slate-500"
              }`}>
                {item.tag}
              </span>
            </Link>
          );
        })}
      </nav>

      {/* Tactical HUD / Target Gauge */}
      <div className="p-3 m-2.5 rounded-xl bg-gradient-to-br from-violet-950/30 via-slate-900 to-cyan-950/20 border border-violet-500/30 shadow-inner">
        <div className="flex items-center justify-between text-[11px] font-bold text-white mb-1.5">
          <span className="flex items-center gap-1 text-cyan-400">
            <Crosshair className="w-3.5 h-3.5" />
            GATE CSE 2027
          </span>
          <span className="font-mono text-violet-300">AIR &lt; 100</span>
        </div>
        <div className="w-full bg-slate-800/80 h-1.5 rounded-full overflow-hidden">
          <div className="bg-gradient-to-r from-violet-500 to-cyan-400 h-full w-[80%] rounded-full shadow-sm shadow-cyan-400/50"></div>
        </div>
        <div className="flex justify-between items-center text-[10px] font-mono text-slate-400 mt-1.5">
          <span>Benchmark</span>
          <span className="text-cyan-300 font-bold">80 / 100</span>
        </div>
      </div>
    </aside>
  );
}
