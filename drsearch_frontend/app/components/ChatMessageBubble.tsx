// app\components\ChatMessageBubble.tsx

import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { emojisplosion } from "emojisplosion";
import { useState, useRef } from "react";
import { useSession } from "next-auth/react"; // Import useSession for authentication
import { SourceBubble, Source } from "./SourceBubble";
import {
  VStack,
  Flex,
  Heading,
  HStack,
  Box,
  Button,
  Divider,
  Spacer,
} from "@chakra-ui/react";
import { sendFeedback } from "../utils/sendFeedback";
import { apiBaseUrl } from "../utils/constants";
import { InlineCitation } from "./InlineCitation";
import DOMPurify from "dompurify";

export type Message = {
  id: string;
  createdAt?: Date;
  content: string;
  role: "system" | "user" | "assistant" | "function";
  runId?: string;
  sources?: Source[];
  name?: string;
  function_call?: { name: string };
};

export type Feedback = {
  feedback_id: string;
  run_id: string;
  key: string;
  score: number;
  comment?: string;
};

export const filterSources = (sources: Source[]) => {
  console.log("Filtering sources:", sources);
  const filtered: Source[] = [];
  const urlMap = new Map<string, number>();
  const indexMap = new Map<number, number>();

  sources.forEach((source, i) => {
    const { url } = source;
    if (url) {
      const index = urlMap.get(url);
      if (index === undefined) {
        urlMap.set(url, i);
        indexMap.set(i, filtered.length);
        filtered.push(source);
      } else {
        const resolvedIndex = indexMap.get(index);
        if (resolvedIndex !== undefined) {
          indexMap.set(i, resolvedIndex);
        }
      }
    } else {
      // Handle the case where url is undefined
      console.warn(
        `Source at index ${i} has undefined url and will be skipped.`,
      );
    }
  });

  console.log("Filtered sources:", filtered);
  console.log("Source index map:", indexMap);
  return { filtered, indexMap };
};

export const createAnswerElements = (
  content: string,
  filteredSources: Source[],
  sourceIndexMap: Map<number, number>,
  highlighedSourceLinkStates: boolean[],
  setHighlightedSourceLinkStates: React.Dispatch<
    React.SetStateAction<boolean[]>
  >,
) => {
  console.log("Creating answer elements with content:", content);
  //const matches = Array.from(content.matchAll(/\[\^?(\d+)\^?\]/g));
  // Adjust regex pattern to match `[${1}]` format
  // const matches = Array.from(content.matchAll(/\[\$\{(\d+)\}\]/g));
  // accept [1]  [$1]  [^1^]  (and still grab the number)
  const citationRegex = /\[\s*[\^\$]?(\d+)[\^\$]?\s*\]/g;
  const matches = Array.from(content.matchAll(citationRegex));
  console.log("Matches found in content:", matches);
  const elements: JSX.Element[] = [];
  let prevIndex = 0;

  matches.forEach((match) => {
    const sourceNum = parseInt(match[1], 10);
    const resolvedNum = sourceIndexMap.get(sourceNum) ?? 10;
    if (match.index !== null && resolvedNum < filteredSources.length) {
      elements.push(
        <span
          key={`content:${prevIndex}`}
          dangerouslySetInnerHTML={{
            __html: DOMPurify.sanitize(content.slice(prevIndex, match.index)),
          }}
        ></span>,
      );
      elements.push(
        <InlineCitation
          key={`citation:${prevIndex}`}
          source={filteredSources[resolvedNum]}
          sourceNumber={sourceNum + 1} // Keep original source number
          highlighted={highlighedSourceLinkStates[resolvedNum]}
          onMouseEnter={() => {
            console.log(
              `Mouse entered citation for source number ${resolvedNum}`,
            );
            setHighlightedSourceLinkStates(
              filteredSources.map((_, i) => i === resolvedNum),
            );
          }}
          onMouseLeave={() => {
            console.log(`Mouse left citation for source number ${resolvedNum}`);
            setHighlightedSourceLinkStates(filteredSources.map(() => false));
          }}
        />,
      );
      prevIndex = (match?.index ?? 0) + match[0].length;
    }
  });

  elements.push(
    <span
      key={`content:${prevIndex}`}
      dangerouslySetInnerHTML={{
        __html: DOMPurify.sanitize(content.slice(prevIndex)),
      }}
    ></span>,
  );

  console.log("Created answer elements:", elements);
  return elements;
};

export function ChatMessageBubble(props: {
  message: Message;
  aiEmoji?: string;
  isMostRecent: boolean;
  messageCompleted: boolean;
}) {
  const { role, content, runId } = props.message;
  console.log("Rendering ChatMessageBubble with props:", props);
  const isUser = role === "user";
  const [isLoading, setIsLoading] = useState(false);
  const [traceIsLoading, setTraceIsLoading] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [comment, setComment] = useState("");
  const [feedbackColor, setFeedbackColor] = useState("");
  const upButtonRef = useRef(null);
  const downButtonRef = useRef(null);

  const { data: session } = useSession(); // Access the session data
  const accessToken = session?.accessToken; // Get the access token from session

  const cumulativeOffset = function (element: HTMLElement | null) {
    var top = 0,
      left = 0;
    do {
      top += element?.offsetTop || 0;
      left += element?.offsetLeft || 0;
      element = (element?.offsetParent as HTMLElement) || null;
    } while (element);

    return {
      top: top,
      left: left,
    };
  };

  const sendUserFeedback = async (score: number, key: string) => {
    console.log(`Sending user feedback with score: ${score}, key: ${key}`);
    let run_id = runId;
    if (run_id === undefined) {
      console.warn("Run ID is undefined, cannot send feedback");
      return;
    }
    if (isLoading) {
      console.warn("Already loading, cannot send feedback");
      return;
    }
    setIsLoading(true);
    try {
      const data = await sendFeedback({
        score,
        runId: run_id,
        key,
        feedbackId: feedback?.feedback_id,
        comment,
        isExplicit: true,
      });
      if (data.code === 200) {
        setFeedback({ run_id, score, key, feedback_id: data.feedbackId });
        score === 1 ? animateButton("upButton") : animateButton("downButton");
        if (comment) {
          setComment("");
        }
        console.log("Feedback sent successfully:", data);
      }
    } catch (e: any) {
      console.error("Error sending feedback:", e);
      toast.error(e.message);
    }
    setIsLoading(false);
  };

  const viewTrace = async () => {
    console.log("Viewing trace for run ID:", runId);
    try {
      setTraceIsLoading(true);
      const response = await fetch(apiBaseUrl + "/get_trace", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`, // Include access token in API request
        },
        body: JSON.stringify({
          run_id: runId,
        }),
      });

      const data = await response.json();

      if (data.code === 400) {
        toast.error("Unable to view trace");
        throw new Error("Unable to view trace");
      } else {
        const url = data.replace(/['"]+/g, "");
        window.open(url, "_blank");
        console.log("Trace URL opened:", url);
        setTraceIsLoading(false);
      }
    } catch (e: any) {
      console.error("Error viewing trace:", e);
      setTraceIsLoading(false);
      toast.error(e.message);
    }
  };

  const sources = props.message.sources ?? [];
  const { filtered: filteredSources, indexMap: sourceIndexMap } =
    filterSources(sources);

  // Use an array of highlighted states as a state since React
  // complains when creating states in a loop
  const [highlighedSourceLinkStates, setHighlightedSourceLinkStates] = useState(
    filteredSources.map(() => false),
  );
  const answerElements =
    role === "assistant"
      ? createAnswerElements(
          content,
          filteredSources,
          sourceIndexMap,
          highlighedSourceLinkStates,
          setHighlightedSourceLinkStates,
        )
      : [];

  const animateButton = (buttonId: string) => {
    console.log(`Animating button with ID: ${buttonId}`);
    let button: HTMLButtonElement | null;
    if (buttonId === "upButton") {
      button = upButtonRef.current;
    } else if (buttonId === "downButton") {
      button = downButtonRef.current;
    } else {
      return;
    }
    if (!button) return;
    let resolvedButton = button as HTMLButtonElement;
    resolvedButton.classList.add("animate-ping");
    setTimeout(() => {
      resolvedButton.classList.remove("animate-ping");
    }, 500);

    emojisplosion({
      emojiCount: 10,
      uniqueness: 1,
      position() {
        const offset = cumulativeOffset(button);

        return {
          x: offset.left + resolvedButton.clientWidth / 2,
          y: offset.top + resolvedButton.clientHeight / 2,
        };
      },
      emojis: buttonId === "upButton" ? ["👍"] : ["👎"],
    });
    console.log("Button animation completed for:", buttonId);
  };

  return (
    <VStack align="start" spacing={5} pb={5}>
      {!isUser && filteredSources.length > 0 && (
        <>
          <Flex direction={"column"} width={"100%"}>
            <VStack spacing={"5px"} align={"start"} width={"100%"}>
              <Heading
                fontSize="lg"
                fontWeight={"medium"}
                mb={1}
                color={"blue.300"}
                paddingBottom={"10px"}
              >
                Sources
              </Heading>
              <HStack spacing={"10px"} maxWidth={"100%"} overflow={"auto"}>
                {filteredSources.map((source, index) => (
                  <Box key={index} alignSelf={"stretch"} width={40}>
                    <SourceBubble
                      source={source}
                      highlighted={highlighedSourceLinkStates[index]}
                      onMouseEnter={() => {
                        console.log(
                          `Mouse entered SourceBubble for index ${index}`,
                        );
                        setHighlightedSourceLinkStates(
                          filteredSources.map((_, i) => i === index),
                        );
                      }}
                      onMouseLeave={() => {
                        console.log(
                          `Mouse left SourceBubble for index ${index}`,
                        );
                        setHighlightedSourceLinkStates(
                          filteredSources.map(() => false),
                        );
                      }}
                      runId={runId}
                    />
                  </Box>
                ))}
              </HStack>
            </VStack>
          </Flex>

          <Heading size="lg" fontWeight="medium" color="blue.300">
            Answer
          </Heading>
        </>
      )}

      {isUser ? (
        <Heading size="lg" fontWeight="medium" color="black">
          <div
            dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(content) }}
          />
        </Heading>
      ) : (
        <Box className="whitespace-pre-wrap" color="black">
          {answerElements}
        </Box>
      )}

      {props.message.role !== "user" &&
        props.isMostRecent &&
        props.messageCompleted && (
          <HStack spacing={2}>
            <Button
              ref={upButtonRef}
              size="sm"
              variant="outline"
              colorScheme={feedback === null ? "green" : "gray"}
              onClick={() => {
                if (feedback === null && props.message.runId) {
                  sendUserFeedback(1, "user_score");
                  animateButton("upButton");
                  setFeedbackColor("border-4 border-green-300");
                } else {
                  toast.error("You have already provided your feedback.");
                }
              }}
            >
              👍
            </Button>
            <Button
              ref={downButtonRef}
              size="sm"
              variant="outline"
              colorScheme={feedback === null ? "red" : "gray"}
              onClick={() => {
                if (feedback === null && props.message.runId) {
                  sendUserFeedback(0, "user_score");
                  animateButton("downButton");
                  setFeedbackColor("border-4 border-red-300");
                } else {
                  toast.error("You have already provided your feedback.");
                }
              }}
            >
              👎
            </Button>
            <Spacer />
            <Button
              size="sm"
              variant="outline"
              colorScheme={runId === null ? "black" : "black"}
              onClick={(e) => {
                e.preventDefault();
                viewTrace();
              }}
              isLoading={traceIsLoading}
              loadingText="🔄"
              color="black"
            >
              🚀🚀 View trace
            </Button>
          </HStack>
        )}

      {!isUser && <Divider mt={4} mb={4} />}
    </VStack>
  );
}
