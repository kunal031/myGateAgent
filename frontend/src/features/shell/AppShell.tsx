"use client";

import React, { Suspense, useEffect, useState } from "react";

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

  // Sidebar and BottomNav read usePathname(), which is only available at
  // runtime. Each needs its own Suspense boundary, or it blocks prerendering
  // of every dynamic route in the app.
  return (
    <div className="min-h-dvh overflow-x-hidden" style={{ background: "var(--canvas)" }}>
      <Suspense fallback={null}>
        <Sidebar open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      </Suspense>
      <TopBar onMenu={() => setDrawerOpen(true)} />

      {/* pb-24 clears the mobile tab bar; md:pl-64 clears the sidebar. */}
      <main className="md:pl-64 min-w-0">
        {/* max-w-[1700px] rather than max-w-5xl: on a wide monitor the old
            1024px cap left several hundred pixels blank on each side and
            forced the card type down to stay readable. */}
        <div className="mx-auto w-full min-w-0 max-w-[1700px] px-4 pb-24 pt-4 md:px-6 md:pb-10 md:pt-6">
          {children}
        </div>
      </main>

      <Suspense fallback={null}>
        <BottomNav />
      </Suspense>
    </div>
  );
}
