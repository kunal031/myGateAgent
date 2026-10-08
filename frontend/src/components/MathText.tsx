"use client";

import React, { useMemo } from "react";
import katex from "katex";

interface MathTextProps {
  text: string;
  className?: string;
}

export default function MathText({ text, className = "" }: MathTextProps) {
  const renderedHtml = useMemo(() => {
    if (!text) return "";

    // Replace display math $$...$$ first
    let processed = text.replace(/\$\$([\s\S]*?)\$\$/g, (_, math) => {
      try {
        return `<div class="my-2.5 overflow-x-auto py-1">${katex.renderToString(math.trim(), {
          displayMode: true,
          throwOnError: false,
        })}</div>`;
      } catch {
        return `<pre class="text-rose-500 font-mono text-xs">${math}</pre>`;
      }
    });

    // Replace inline math $...$
    processed = processed.replace(/\$([^\$\n]+?)\$/g, (_, math) => {
      try {
        return katex.renderToString(math.trim(), {
          displayMode: false,
          throwOnError: false,
        });
      } catch {
        return `<code class="text-rose-500">${math}</code>`;
      }
    });

    // Simple markdown formatting for bold and code backticks and newlines
    processed = processed
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.*?)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-[var(--surface-sunk)] text-amber-300 font-mono text-xs">$1</code>')
      .replace(/\n\n/g, '<div class="h-2"></div>')
      .replace(/\n/g, "<br/>");

    return processed;
  }, [text]);

  return (
    <div
      className={`leading-relaxed ${className}`}
      dangerouslySetInnerHTML={{ __html: renderedHtml }}
    />
  );
}
