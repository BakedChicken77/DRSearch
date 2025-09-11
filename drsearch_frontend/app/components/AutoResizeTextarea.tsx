import React, { useImperativeHandle, useRef, useState } from "react";
import { Textarea, TextareaProps } from "@chakra-ui/react";
import ResizeTextarea from "react-textarea-autosize";
import { expandLastAcronym } from "../utils/acronyms";

interface Replacement {
  acronym: string;
  expansion: string;
  start: number;
  end: number;
}

interface AutoResizeTextareaProps extends TextareaProps {
  value: string;
  onChange: (val: string) => void;
  acronymMap: Record<string, string>;
}

export const AutoResizeTextarea = React.forwardRef<
  HTMLTextAreaElement,
  AutoResizeTextareaProps
>(({ value, onChange, acronymMap, onKeyDown, ...props }, ref) => {
  const innerRef = useRef<HTMLTextAreaElement | null>(null);
  useImperativeHandle(ref, () => innerRef.current as HTMLTextAreaElement);
  const [replacements, setReplacements] = useState<Replacement[]>([]);

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
      requestAnimationFrame(() => {
        innerRef.current?.setSelectionRange(start, end);
        requestAnimationFrame(() => {
          const pos = innerRef.current?.value.length ?? 0;
          innerRef.current?.setSelectionRange(pos, pos);
        });
      });
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
                ? { ...r, start: r.start - diff, end: r.end - diff }
                : r,
            ),
        );
        const caret = rep.start + rep.acronym.length + 1;
        el.setSelectionRange(caret, caret);
        return;
      }
    }
    onKeyDown?.(e);
  };

  return (
    <Textarea
      as={ResizeTextarea}
      ref={innerRef}
      value={value}
      onChange={handleChange}
      onKeyDown={handleKeyDown}
      {...props}
    />
  );
});

AutoResizeTextarea.displayName = "AutoResizeTextarea";
