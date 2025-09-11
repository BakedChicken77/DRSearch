// app\components\AcronymTextarea.tsx

import React, { useMemo, useRef, useState, useImperativeHandle } from "react";
import { Textarea, TextareaProps } from "@chakra-ui/react";
import ResizeTextarea from "react-textarea-autosize";
import { expandLastAcronym } from "../utils/acronyms";

interface Replacement {
  acronym: string;
  expansion: string;
  start: number;
  end: number;
}

interface AcronymTextareaProps extends TextareaProps {
  value: string;
  onChange: (val: string) => void;
  acronymMap: Record<string, string>;
}

export const AcronymTextarea = React.forwardRef<
  HTMLTextAreaElement,
  AcronymTextareaProps
>(({ value, onChange, acronymMap, onKeyDown, ...props }, ref) => {
  const innerRef = useRef<HTMLTextAreaElement | null>(null);
  useImperativeHandle(ref, () => innerRef.current as HTMLTextAreaElement);
  const [replacements, setReplacements] = useState<Replacement[]>([]);

  const renderWithHighlights = useMemo(() => {
    let result = "";
    let lastIndex = 0;
    const text = value;
    replacements.forEach((r) => {
      result += escapeHtml(text.slice(lastIndex, r.start));
      result += `<span class="acronym-replacement">${escapeHtml(
        text.slice(r.start, r.end),
      )}</span>`;
      lastIndex = r.end;
    });
    result += escapeHtml(text.slice(lastIndex));
    return result;
  }, [value, replacements]);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    const isDeleting = val.length < value.length;
    if (isDeleting) {
      onChange(val);
      setReplacements((rs) => rs.filter((r) => r.end <= val.length));
      return;
    }
    const { text, acronym, expansion, start } = expandLastAcronym(
      val,
      acronymMap,
    );
    if (acronym && expansion && typeof start === "number") {
      const end = start + expansion.length;
      setReplacements((rs) => [...rs, { acronym, expansion, start, end }]);
      e.target.value = text;
      onChange(text);
    } else {
      onChange(val);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Backspace") {
      const el = innerRef.current;
      if (!el) return;
      const pos = el.selectionStart;
      const idx = replacements.findIndex((r) => pos === r.end + 1);
      if (idx !== -1) {
        e.preventDefault();
        const rep = replacements[idx];
        const before = el.value.slice(0, rep.start);
        const after = el.value.slice(rep.end + 1);
        const newText = before + rep.acronym + " " + after;
        const diff = rep.expansion.length - rep.acronym.length;
        el.value = newText;
        onChange(newText);
        setReplacements((rs) =>
          rs
            .filter((_, i) => i !== idx)
            .map((r) =>
              r.start > rep.start
                ? {
                    ...r,
                    start: r.start - diff,
                    end: r.end - diff,
                  }
                : r,
            ),
        );
        el.selectionStart = el.selectionEnd =
          rep.start + rep.acronym.length + 1;
        return;
      }
    }
    onKeyDown?.(e);
  };

  return (
    <div style={{ position: "relative", width: "100%" }}>
      <div
        data-testid="acronym-overlay"
        aria-hidden="true"
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          color: "black",
          pointerEvents: "none",
          zIndex: 0,
        }}
        dangerouslySetInnerHTML={{ __html: renderWithHighlights }}
      />
      <Textarea
        as={ResizeTextarea}
        ref={innerRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        style={{
          position: "relative",
          background: "transparent",
          color: "transparent",
          caretColor: "black",
          zIndex: 1,
        }}
        {...props}
      />
    </div>
  );
});

AcronymTextarea.displayName = "AcronymTextarea";

function escapeHtml(text: string) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
