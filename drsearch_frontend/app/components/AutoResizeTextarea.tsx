// app\components\AutoResizeTextarea.tsx

import { Textarea, TextareaProps } from "@chakra-ui/react";
import ResizeTextarea from "react-textarea-autosize";
import React from "react";

interface ResizeTextareaProps {
  maxRows?: number;
}

const ResizableTextarea = React.forwardRef<
  HTMLTextAreaElement,
  ResizeTextareaProps
>(({ maxRows, ...props }, ref) => (
  <ResizeTextarea maxRows={maxRows} ref={ref} {...props} />
));

ResizableTextarea.displayName = "ResizableTextarea";

interface AutoResizeTextareaProps extends TextareaProps {
  maxRows?: number;
}

export const AutoResizeTextarea = React.forwardRef<
  HTMLTextAreaElement,
  AutoResizeTextareaProps
>((props, ref) => {
  return (
    <Textarea
      minH="unset"
      overflow="auto"
      w="100%"
      resize="none"
      ref={ref as React.RefObject<HTMLTextAreaElement>}
      as={ResizableTextarea}
      {...props}
    />
  );
});

AutoResizeTextarea.displayName = "AutoResizeTextarea";
