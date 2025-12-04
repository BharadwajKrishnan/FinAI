"use client";

interface MarkdownRendererProps {
  content: string;
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  // Simple markdown parser for basic formatting
  const parseMarkdown = (text: string): React.ReactNode => {
    const lines = text.split("\n");
    const elements: React.ReactNode[] = [];
    let currentList: string[] = [];
    let inList = false;

    const flushList = () => {
      if (currentList.length > 0) {
        elements.push(
          <ul key={`list-${elements.length}`} className="list-disc list-inside space-y-1 my-2 ml-4">
            {currentList.map((item, idx) => (
              <li key={idx} className="text-sm">
                {parseInlineMarkdown(item.trim())}
              </li>
            ))}
          </ul>
        );
        currentList = [];
      }
      inList = false;
    };

    lines.forEach((line, index) => {
      const trimmed = line.trim();

      // Check for bullet points (starts with *, -, or •, with optional spaces)
      // Matches: "* text", "*   text", "- text", etc.
      if (/^[\*\-\•]\s+/.test(trimmed) || /^[\*\-\•]/.test(trimmed)) {
        if (!inList) {
          flushList();
          inList = true;
        }
        // Remove the bullet marker and any leading spaces
        const listItem = trimmed.replace(/^[\*\-\•]\s*/, "").trim();
        if (listItem) {
          currentList.push(listItem);
        }
        return;
      }

      // Check for numbered lists (1. text, 2. text, etc.)
      if (/^\d+\.\s+/.test(trimmed) || /^\d+\./.test(trimmed)) {
        if (!inList) {
          flushList();
          inList = true;
        }
        // Remove the number and period, and any leading spaces
        const listItem = trimmed.replace(/^\d+\.\s*/, "").trim();
        if (listItem) {
          currentList.push(listItem);
        }
        return;
      }

      // Flush list if we hit a non-list line
      if (inList) {
        flushList();
      }

      // Empty line
      if (trimmed === "") {
        elements.push(<br key={`br-${index}`} />);
        return;
      }

      // Headers
      if (trimmed.startsWith("### ")) {
        elements.push(
          <h3 key={`h3-${index}`} className="text-base font-semibold mt-4 mb-2">
            {parseInlineMarkdown(trimmed.substring(4))}
          </h3>
        );
        return;
      }
      if (trimmed.startsWith("## ")) {
        elements.push(
          <h2 key={`h2-${index}`} className="text-lg font-semibold mt-4 mb-2">
            {parseInlineMarkdown(trimmed.substring(3))}
          </h2>
        );
        return;
      }
      if (trimmed.startsWith("# ")) {
        elements.push(
          <h1 key={`h1-${index}`} className="text-xl font-bold mt-4 mb-2">
            {parseInlineMarkdown(trimmed.substring(2))}
          </h1>
        );
        return;
      }

      // Regular paragraph
      elements.push(
        <p key={`p-${index}`} className="my-2">
          {parseInlineMarkdown(trimmed)}
        </p>
      );
    });

    // Flush any remaining list
    flushList();

    return elements.length > 0 ? <>{elements}</> : <p>{content}</p>;
  };

  const parseInlineMarkdown = (text: string): React.ReactNode => {
    if (!text) return text;
    
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let keyCounter = 0;

    // Match bold **text** or __text__ (non-greedy)
    const boldRegex = /(\*\*|__)(.+?)\1/g;
    let match;

    while ((match = boldRegex.exec(text)) !== null) {
      // Add text before the match
      if (match.index > lastIndex) {
        const beforeText = text.substring(lastIndex, match.index);
        if (beforeText) {
          parts.push(beforeText);
        }
      }
      // Add bold text
      parts.push(<strong key={`bold-${keyCounter++}`}>{match[2]}</strong>);
      lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      const remainingText = text.substring(lastIndex);
      if (remainingText) {
        parts.push(remainingText);
      }
    }

    return parts.length > 0 ? <>{parts}</> : text;
  };

  return <div className="markdown-content">{parseMarkdown(content)}</div>;
}

