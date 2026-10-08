import type { Metadata } from "next";
import "katex/dist/katex.min.css";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "GateMaster | GATE CSE 2027 (Target 80+ Marks)",
  description: "Targeted preparation, active recall feed, drills, and RAG tutor for GATE CSE 2027.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark h-full">
      <body className="font-sans bg-slate-950 text-slate-100 min-h-full flex antialiased">
        <Sidebar />
        <main className="ml-64 flex-1 min-h-screen bg-slate-950 p-6 md:p-8">
          {children}
        </main>
      </body>
    </html>
  );
}
