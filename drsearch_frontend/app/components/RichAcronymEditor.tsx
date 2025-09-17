// app/components/RichAcronymEditor.tsx
"use client";

import React, { useEffect } from "react";
import { Box } from "@chakra-ui/react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Extension, InputRule } from "@tiptap/core";
import { Mark, mergeAttributes } from "@tiptap/core";

/** Convert plain text into minimal HTML paragraphs so TipTap is happy */
function valueToHtml(text: string) {
  const safe = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  // Split double newlines into paragraphs; single newline -> <br>
  return safe
    .split("\n\n")
    .map((p) => `<p>${p.replace(/\n/g, "<br>") || "<br>"}</p>`)
    .join("");
}

function expansionAttrsFromProps(
  expansionStyle?: ExpansionAttrs,
  expansionClass?: string,
): ExpansionAttrs {
  return { ...(expansionStyle || {}), class: expansionClass ?? expansionStyle?.class ?? undefined };
}



type ExpansionAttrs = {
  color?: string;
  fontFamily?: string;
  fontSize?: string;
  fontWeight?: string;
  fontStyle?: string;       // e.g., "italic"
  backgroundColor?: string;
  class?: string;
};

const ExpansionMark = Mark.create({
  name: "expansion",
  addAttributes() {
    return {
      color: { default: null },
      fontFamily: { default: null },
      fontSize: { default: null },
      fontWeight: { default: null },
      fontStyle: { default: null },
      backgroundColor: { default: null },
      class: { default: null },
    };
  },
  parseHTML() {
    return [{ tag: "span[data-expansion]" }];
  },
  renderHTML({ HTMLAttributes }) {
    const { class: cls, ...styleable } = HTMLAttributes as ExpansionAttrs;
    const style: Record<string, string> = {};
    if (styleable.color) style.color = styleable.color;
    if (styleable.fontFamily) style.fontFamily = styleable.fontFamily;
    if (styleable.fontSize) style.fontSize = styleable.fontSize;
    if (styleable.fontWeight) style.fontWeight = styleable.fontWeight;
    if (styleable.fontStyle) style.fontStyle = styleable.fontStyle;
    if (styleable.backgroundColor) style.backgroundColor = styleable.backgroundColor;

    return [
      "span",
      mergeAttributes(
        { "data-expansion": "true" },
        cls ? { class: cls } : {},
        { style: Object.entries(style).map(([k, v]) => `${k}:${v}`).join(";") }
      ),
      0,
    ];
  },
});

/* =========================
   Types & Props
   ========================= */
type AcronymMap = Record<string, string>;

export interface RichAcronymEditorProps {
  value: string;                          // plain text in outer state
  onChange: (val: string) => void;        // plain text change
  acronymMap: AcronymMap;                 // { HR: "Human Resources", ... }
  isDisabled?: boolean;
  placeholder?: string;
  onSubmit?: (text: string) => void;
  

  /** Optional: inline style attributes for expansion mark */
  expansionStyle?: ExpansionAttrs;

  /** Optional: CSS class appended to expansion mark (works with globals.css) */
  expansionClass?: string; // e.g., "expansion--blue"
}

/* =========================
   Helpers
   ========================= */

// Delimiters that should trigger expansion and be preserved
const DELIMS = [" ", ",", ".", ";", ":", "!", "?", "\n"] as const;
type Delim = (typeof DELIMS)[number];

// Undo expansion if text ends with "<expansion><delim>" at caret end (chat-style)
function undoExpansionAtEnd(editor: any, acronymMap: AcronymMap) {
  const { from, to } = editor.state.selection;
  if (from !== to) return false; // only caret
  const atEnd = from === editor.state.doc.content.size;
  if (!atEnd) return false;

  const text: string = editor.getText();

  for (const [acr, exp] of Object.entries(acronymMap)) {
    for (const delim of DELIMS) {
      const needle = exp + delim;
      if (text.endsWith(needle)) {
        const expLen = exp.length;
        const delimLen = delim.length;
        const tokenFrom = from - (expLen + delimLen);
        const tokenTo = from - delimLen;

        editor
          .chain()
          .focus()
          .setTextSelection({ from: tokenFrom, to: tokenTo })
          .insertContent([
            { type: "text", text: acr },
            { type: "text", text: delim },
          ])
          .setTextSelection(from - (expLen - acr.length))
          .run();

        return true;
      }
    }
  }
  return false;
}

/* =========================
   Keyboard shortcuts extension
   ========================= */
function Shortcuts(onSubmit?: (text: string) => void, acronymMap?: AcronymMap, markAttrs?: ExpansionAttrs) {
  return Extension.create({
    name: "acronymShortcuts",
    /** Ensure our keymap wins over StarterKit’s */
    priority: 1000,
    addKeyboardShortcuts() {
      return {
        // Shift+Enter => newline
        "Shift-Enter": () => this.editor.commands.setHardBreak(),

        // Ctrl/Cmd+Enter => newline
        "Mod-Enter": () => this.editor.commands.setHardBreak(),

        // Backspace: undo immediate expansion if we're right after it
        Backspace: () => {
          if (!acronymMap) return false;
          return undoExpansionAtEnd(this.editor, acronymMap) || false;
        },

        // Enter: expand bare acronym if present; otherwise send
        Enter: () => {
          const editor = this.editor;
          const { from, to } = editor.state.selection;
          if (from !== to) return false; // allow default behavior for ranged selections

          const text = editor.getText();

          // Try bare-acronym expansion first
          if (acronymMap && text.length > 0) {
            const m = text.match(/([A-Za-z0-9_]+)$/);
            if (m) {
              const token = m[1];
              const exp = acronymMap[token.toUpperCase()];
              if (exp) {
                const tokenFrom = from - token.length;
                editor
                  .chain()
                  .focus()
                  .setTextSelection({ from: tokenFrom, to: from })
                  .deleteSelection()
                  .insertContent([{ type: "text", text: exp, marks: [{ type: "expansion", attrs: markAttrs }] }])
                  .setTextSelection(tokenFrom + exp.length)
                  .run();

                return true; // expanded; user presses Enter again to send
              }
            }
          }

          // Nothing to expand → send (if provided)
          onSubmit?.(editor.getText());   // submit the live text
          return true; // prevent default newline
        },
      };
    },
  });
}

/* =========================
   Input Rule for delimiter-triggered expansion
   ========================= */
/**
 * Fires when the user types a delimiter after a token at the end of a textblock.
 * Regex captures the token and the delimiter, so we can:
 *  - replace just the token with the expansion (styled with italic mark)
 *  - then re-insert the delimiter unchanged
 */
function AcronymExpansion(acronymMap: AcronymMap, markAttrs: ExpansionAttrs) {
  const rx = /([A-Za-z0-9_]+)([ \t.,;:!? ])$/;
  return Extension.create({
    name: "acronymExpansion",
    addInputRules() {
      return [
        new InputRule({
          find: rx,
          handler: ({ range, match, chain }) => {
            const token = match[1];
            const delim = match[2] as Delim;
            const exp = acronymMap[token.toUpperCase()];
            if (!exp) return;

            // The input rule range covers TOKEN + DELIM
            const fullFrom = range.from;
            const fullTo = range.to;

            // Replace the full match (token+delim) with [expansion(italic), delim]
            chain()
              .setTextSelection({ from: fullFrom, to: fullTo })
              .deleteSelection()
              .insertContent([
                { type: "text", text: exp, marks: [{ type: "expansion", attrs: markAttrs }] },
                { type: "text", text: delim },
              ])
              // caret ends after the delimiter
              .setTextSelection(fullFrom + exp.length + delim.length)
              .run();
          },
        }),
      ];
    },
  });
}
/* =========================
   Component
   ========================= */
export default function RichAcronymEditor({
  value,
  onChange,
  acronymMap,
  isDisabled,
  placeholder,
  onSubmit,
  expansionStyle,      
  expansionClass="expansion--darkblue",  
}: RichAcronymEditorProps) {

  const markAttrs = expansionAttrsFromProps(expansionStyle, expansionClass);
  const editor = useEditor(
    {
      extensions: [
        StarterKit,                         // paragraphs, marks, hardBreak, etc.
        ExpansionMark,  
        AcronymExpansion(acronymMap, markAttrs),       // <— expand on delimiter via InputRule
        Shortcuts(onSubmit, acronymMap, markAttrs),    // Enter / Shift+Enter / Mod+Enter / Backspace
      ],
      content: valueToHtml(value),
      editable: !isDisabled,
      onUpdate: ({ editor }) => {
        onChange(editor.getText());
      },
      immediatelyRender: false,             // avoid Next.js hydration mismatch
    },
    [isDisabled, acronymMap, expansionStyle, expansionClass]                // re-init rules when map changes
  );

  // Keep editor in sync if outer plain text is externally cleared/changed
  useEffect(() => {
    if (!editor) return;
    const current = editor.getText();
    if (current !== value) {
      editor.commands.setContent(valueToHtml(value), { emitUpdate: false });
    }
  }, [value, editor]);

  return (
    <Box
      className="tiptap-wrapper"
      border="1px solid rgb(58, 58, 61)"
      borderRadius="md"
      p={2}
      bg={isDisabled ? "gray.200" : "white"}
      cursor={isDisabled ? "not-allowed" : "text"}
      opacity={isDisabled ? 0.7 : 1}
      position="relative"
      minH="2.75rem"
    >
      {placeholder && !value && (
        <Box color="gray.500" position="absolute" pointerEvents="none">
          {placeholder}
        </Box>
      )}

      {editor && <EditorContent editor={editor} className="tiptap" />}

      <style jsx global>{`
        .tiptap {
          outline: none;
          white-space: pre-wrap;
          word-break: break-word;
        }
        /* Style expansions inline. We're using the built-in italic mark. */
        .tiptap em {
          font-style: italic;
          font-family: "Times New Roman", serif; /* your special font */
        }
      `}</style>
    </Box>
  );
}
