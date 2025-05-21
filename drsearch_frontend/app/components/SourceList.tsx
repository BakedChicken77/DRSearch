import { VStack, Link } from "@chakra-ui/react";
import { Source } from "./SourceBubble";
import { sendFeedback } from "../utils/sendFeedback";
import { convertToHttpUrlIfNeeded } from "../utils/urlUtils";

export function SourceList({
  sources,
  highlightedStates,
  onMouseEnter,
  onMouseLeave,
  runId,
}: {
  sources: Source[];
  highlightedStates: boolean[];
  onMouseEnter: (index: number) => void;
  onMouseLeave: () => void;
  runId?: string;
}) {
  return (
    <VStack align="start" spacing={1}>
      {sources.map((source, index) => {
        const fileUrl = source.url ? convertToHttpUrlIfNeeded(source.url) : "";
        const fileTitle = source.title || "Unknown Document";
        return (
          <Link
            key={index}
            color={highlightedStates[index] ? "blue.200" : "blue.300"}
            onMouseEnter={() => onMouseEnter(index)}
            onMouseLeave={onMouseLeave}
            onClick={async () => {
              if (fileUrl) {
                const a = document.createElement("a");
                a.href = fileUrl;
                a.target = "_blank";
                a.rel = "noopener noreferrer";
                a.style.display = "none";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
              }
              if (runId) {
                await sendFeedback({
                  key: "user_click",
                  runId,
                  value: fileUrl,
                  isExplicit: false,
                });
              }
            }}
          >
            {fileTitle}
          </Link>
        );
      })}
    </VStack>
  );
}
