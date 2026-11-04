"use client";

import React, { useMemo } from "react";
import katex from "katex";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";

interface MathTextProps {
  text: string;
  className?: string;
}

/**
 * Renders a tutor answer: GitHub-flavoured markdown with TeX in it.
 *
 * This used to be a chain of regexes handling `**bold**`, backticks and
 * newlines. It could not do tables, headings or lists, so an answer like
 * the assistant actually writes -- `## Deadlock`, a four-column
 * comparison table, numbered steps -- arrived as literal `##` and `|`
 * characters down the page. Those tables are the useful part of a
 * revision answer, so the fix is to render them rather than to stop the
 * model producing them.
 *
 * Math is pre-rendered to HTML by KaTeX before the markdown pass,
 * because react-markdown would otherwise escape the TeX. `\[...\]` and
 * `\(...\)` are normalised to `$$`/`$` first: models emit those LaTeX
 * delimiters freely and KaTeX does not recognise them, which is why
 * formulas showed up raw.
 */

/** KaTeX output is trusted (we generated it); everything else in the
 *  source is escaped by react-markdown as usual. */
function renderMath(source: string): string {
  let out = source;

  // \[ ... \] -> $$ ... $$   and   \( ... \) -> $ ... $
  out = out.replace(/\\\[([\s\S]*?)\\\]/g, (_, m) => `$$${m}$$`);
  out = out.replace(/\\\(([\s\S]*?)\\\)/g, (_, m) => `$${m}$`);

  const display = (math: string) => {
    try {
      return katex.renderToString(math.trim(), {
        displayMode: true,
        throwOnError: false,
      });
    } catch {
      return `<code>${math}</code>`;
    }
  };
  const inline = (math: string) => {
    try {
      return katex.renderToString(math.trim(), {
        displayMode: false,
        throwOnError: false,
      });
    } catch {
      return `<code>${math}</code>`;
    }
  };

  out = out.replace(/\$\$([\s\S]*?)\$\$/g, (_, m) => display(m));
  // Single-line only, so a lone `$` in prose cannot swallow a paragraph.
  out = out.replace(/\$([^$\n]+?)\$/g, (_, m) => inline(m));
  return out;
}

export default function MathText({ text, className = "" }: MathTextProps) {
  const source = useMemo(() => renderMath(text || ""), [text]);

  if (!text) return null;

  return (
    <div className={`space-y-2 ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        // KaTeX emits raw HTML. Without rehype-raw react-markdown drops
        // it silently -- verified: every formula disappeared rather than
        // rendering. The only HTML reaching this plugin is KaTeX output
        // we generated ourselves a few lines above; the model's own text
        // is escaped before it gets here.
        rehypePlugins={[rehypeRaw]}
        components={{

          h1: ({ children }) => (
            <h3 className="mt-3 text-[14px] font-extrabold" style={{ color: "var(--ink)" }}>{children}</h3>
          ),
          h2: ({ children }) => (
            <h3 className="mt-3 text-[13.5px] font-extrabold" style={{ color: "var(--ink)" }}>{children}</h3>
          ),
          h3: ({ children }) => (
            <h4 className="mt-2.5 text-[12.5px] font-bold" style={{ color: "var(--ink)" }}>{children}</h4>
          ),
          h4: ({ children }) => (
            <h5 className="mt-2 text-[12px] font-bold" style={{ color: "var(--ink-soft)" }}>{children}</h5>
          ),

          p: ({ children }) => <p className="leading-relaxed">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-bold" style={{ color: "var(--ink)" }}>{children}</strong>
          ),

          ul: ({ children }) => (
            <ul className="list-disc space-y-1 pl-5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal space-y-1 pl-5">{children}</ol>
          ),

          // The reason this component exists. Scrolls rather than
          // overflowing: a four-column GATE comparison does not fit a
          // chat bubble on a phone.
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto">
              <table className="w-full border-collapse text-[12px]">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="px-2 py-1.5 text-left align-top font-extrabold"
                style={{
                  borderBottom: "var(--line-width) solid var(--line)",
                  background: "var(--surface-sunk)",
                  color: "var(--ink)",
                }}>
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-2 py-1.5 align-top"
                style={{ borderBottom: "var(--line-width) solid var(--line)" }}>
              {children}
            </td>
          ),

          code: ({ className: cls, children }) => {
            const fenced = (cls || "").startsWith("language-");
            if (fenced) {
              return (
                <code className="block overflow-x-auto rounded p-2 font-mono text-[11.5px]"
                      style={{ background: "var(--surface-sunk)" }}>
                  {children}
                </code>
              );
            }
            return (
              <code className="rounded px-1.5 py-0.5 font-mono text-[11.5px]"
                    style={{ background: "var(--surface-sunk)", color: "var(--accent)" }}>
                {children}
              </code>
            );
          },
          pre: ({ children }) => <pre className="my-2">{children}</pre>,

          blockquote: ({ children }) => (
            <blockquote className="my-2 pl-3 italic"
                        style={{ borderLeft: "2px solid var(--line)", color: "var(--ink-soft)" }}>
              {children}
            </blockquote>
          ),
          hr: () => (
            <hr className="my-3" style={{ borderColor: "var(--line)" }} />
          ),
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer"
               className="underline underline-offset-2" style={{ color: "var(--accent)" }}>
              {children}
            </a>
          ),
        }}
      >
        {source}
      </ReactMarkdown>
    </div>
  );
}
