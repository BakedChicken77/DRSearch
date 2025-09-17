import { VStack, Link } from "@chakra-ui/react";
import { Source } from "./SourceBubble";
import { sendFeedback } from "../utils/sendFeedback";
import { convertToHttpUrlIfNeeded } from "../utils/urlUtils";
import { useSession } from "next-auth/react";

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
  const { data: session } = useSession();
  const accessToken = session?.accessToken as string | undefined;
  return (
    <VStack align="start" spacing={1}>
      {sources.map((source, index) => {
        const fileUrl = source.url ? convertToHttpUrlIfNeeded(source.url) : "";
        const fileTitle = source.title || "Unknown Document";
        return (
          <Link
            key={index}
            className={`source-list-link ${highlightedStates[index] ? "is-highlighted" : ""}`}
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
                  accessToken,
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
