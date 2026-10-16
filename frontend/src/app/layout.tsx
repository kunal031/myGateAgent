import type { Metadata, Viewport } from "next";
import "katex/dist/katex.min.css";
import "../styles/themes.css";
import "./globals.css";

import AppShell from "@/features/shell/AppShell";
import AuthGate from "@/features/auth/AuthGate";
import AuthProvider from "@/features/auth/AuthProvider";
import { THEME_INIT_SCRIPT, ThemeProvider } from "@/features/theme/ThemeProvider";

export const metadata: Metadata = {
  title: "GateMaster | GATE CSE 2027",
  description:
    "Targeted preparation, active recall feed, drills, and RAG tutor for GATE CSE 2027.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // viewportFit lets the layout use env(safe-area-inset-*) on notched phones.
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Applies the stored theme before first paint, avoiding a flash of
            the default theme on load. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="antialiased">
        <ThemeProvider>
          {/* Gating at the root means a new route is protected by default;
              guarding page by page fails quietly, and the failure is an
              unprotected screen. */}
          <AuthProvider>
            <AuthGate>
              <AppShell>{children}</AppShell>
            </AuthGate>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
