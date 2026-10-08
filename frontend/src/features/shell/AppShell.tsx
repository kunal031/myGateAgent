"use client";

import React, { useEffect, useState } from "react";

import BottomNav from "./BottomNav";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Lock background scroll while the drawer covers the screen.
  useEffect(() => {
    if (!drawerOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [drawerOpen]);

  return (
    <div className="min-h-dvh overflow-x-hidden" style={{ background: "var(--canvas)" }}>
      <Sidebar open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      <TopBar onMenu={() => setDrawerOpen(true)} />

      {/* pb-24 clears the mobile tab bar; md:pl-64 clears the sidebar. */}
      <main className="md:pl-64 min-w-0">
        <div className="mx-auto w-full min-w-0 max-w-5xl px-4 pb-24 pt-4 md:px-8 md:pb-10 md:pt-8">
          {children}
        </div>
      </main>

      <BottomNav />
    </div>
  );
}
