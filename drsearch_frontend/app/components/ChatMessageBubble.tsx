// app\components\ChatMessageBubble.tsx

import { toast } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { emojisplosion } from "emojisplosion";
import { useState, useRef } from "react";
import { useSession } from "next-auth/react"; // Import useSession for authentication
import { Source } from "./SourceBubble";
import { SourceList } from "./SourceList";
import {
  VStack,
  Flex,
  Heading,
  HStack,
  Box,
  Button,
  Divider,
  Spacer,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody as ChakraModalBody,
  ModalCloseButton,
  Textarea,
  StackDivider
} from "@chakra-ui/react";
import { sendFeedback } from "../utils/sendFeedback";

import { InlineCitation } from "./InlineCitation";
import DOMPurify from "dompurify";


export const __TEST__ = {
  sendUserFeedback: null as
    | ((score: number | null, key: string) => Promise<void>)
    | null,
  animateButton: null as ((buttonId: string) => void) | null,

  setComment: null as ((c: string) => void) | null,
  comment: "",
};

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
  score: number | null;
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

export const filterSourcesByCitations = (
  content: string,
  filteredSources: Source[],
  sourceIndexMap: Map<number, number>,
) => {
  const citationRegex = /\[\s*[\^\$]?(\d+)[\^\$]?\s*\]/g;
  const matches = Array.from(content.matchAll(citationRegex));
  const citedOriginal = new Set<number>();
  matches.forEach((match) => {
    citedOriginal.add(parseInt(match[1], 10));
  });

  const usedDedup = new Set<number>();
  citedOriginal.forEach((orig) => {
    const dedup = sourceIndexMap.get(orig);
    if (dedup !== undefined) {
      usedDedup.add(dedup);
    }
  });

  const remap = new Map<number, number>();
  const newFiltered: Source[] = [];
  filteredSources.forEach((src, idx) => {
    if (usedDedup.has(idx)) {
      remap.set(idx, newFiltered.length);
      newFiltered.push(src);
    }
  });

  const newIndexMap = new Map<number, number>();
  sourceIndexMap.forEach((dedupIdx, origIdx) => {
    const newIdx = remap.get(dedupIdx);
    if (newIdx !== undefined) {
      newIndexMap.set(origIdx, newIdx);
    }
  });

  return { filteredSources: newFiltered, indexMap: newIndexMap };
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
    const mappedIndex = sourceIndexMap.get(sourceNum);
    const fallbackIndex =
      filteredSources.length > 0 ? filteredSources.length - 1 : undefined;
    const resolvedNum = mappedIndex ?? fallbackIndex ?? -1;
    const displayNumber =
      mappedIndex !== undefined && resolvedNum >= 0
        ? resolvedNum + 1
        : sourceNum + 1;

    if (
      match.index !== null &&
      resolvedNum >= 0 &&
      resolvedNum < filteredSources.length
    ) {
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
          sourceNumber={displayNumber}
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
  conversation: Message[];
}) {
  const { role, content, runId } = props.message;
  console.log("Rendering ChatMessageBubble with props:", props);
  const isUser = role === "user";
  const [isLoading, setIsLoading] = useState(false);

  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [comment, setComment] = useState("");
  __TEST__.setComment = setComment;
  __TEST__.comment = comment;
  const [feedbackColor, setFeedbackColor] = useState("");
  const upButtonRef = useRef(null);
  const downButtonRef = useRef(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [pendingScore, setPendingScore] = useState<number | null>(null);

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

  const sendUserFeedback = async (score: number | null, key: string) => {
    console.log(`Sending user feedback with score: ${score}, key: ${key}`);
    let run_id = runId;
    if (run_id === undefined) {
      /* istanbul ignore next */
      console.warn("Run ID is undefined, cannot send feedback");
      /* istanbul ignore next */
      return;
    }
    if (isLoading) {
      console.warn("Already loading, cannot send feedback");
      return;
    }
    setIsLoading(true);
    try {
      const data = await sendFeedback({
        score: score ?? undefined,
        runId: run_id,
        key,
        feedbackId: feedback?.feedback_id,
        comment,
        conversation: props.conversation.map((m) => ({
          role: m.role,
          content: m.content,
        })),
        documents: props.message.sources?.map((s) => s.url) ?? [],
        accessToken,
        isExplicit: true,
      });
      if (data.code === 200) {
        setFeedback({ run_id, score, key, feedback_id: data.feedbackId });
        if (score !== null) {
          score === 1 ? animateButton("upButton") : animateButton("downButton");
        }
        if (comment) {
          /* istanbul ignore next */
          setComment("");
        }
        console.log("Feedback sent successfully:", data);
      }
    } catch (e: any) {
      /* istanbul ignore next */
      console.error("Error sending feedback:", e);
      /* istanbul ignore next */
      toast.error(e.message);
    }
    setIsLoading(false);
  };
  __TEST__.sendUserFeedback = sendUserFeedback;



  const sources = props.message.sources ?? [];
  const { filtered: dedupedSources, indexMap: initialIndexMap } =
    filterSources(sources);
  const { filteredSources, indexMap: sourceIndexMap } =
    filterSourcesByCitations(content, dedupedSources, initialIndexMap);

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
    /* istanbul ignore next */
    let button: HTMLButtonElement | null;
    if (buttonId === "upButton") {
      button = upButtonRef.current;
    } else if (buttonId === "downButton") {
      button = downButtonRef.current;
    } else {
      /* istanbul ignore next */
      return;
    }
    if (!button) return;
    let resolvedButton = button as HTMLButtonElement;
    resolvedButton.classList.add("animate-ping"); // istanbul ignore next
    setTimeout(() => {
      resolvedButton.classList.remove("animate-ping");
    }, 500); // istanbul ignore next

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
  __TEST__.animateButton = animateButton;

  return (
    <VStack align="start" spacing={5} pb={5}>
      {!isUser && filteredSources.length > 0 && (
        <>
          <VStack
            spacing="8px"
            align="start"
            width="100%"
            divider={<StackDivider borderColor="gray.200" />}
          >
            <Heading
              fontSize="lg"
              fontWeight="medium"
              mb={1}
              className="view-sources-title"
              paddingBottom="6px"
            >
              View Sources
            </Heading>

            <SourceList
              sources={filteredSources}
              highlightedStates={highlighedSourceLinkStates}
              onMouseEnter={(index) => {
                setHighlightedSourceLinkStates(
                  filteredSources.map((_, i) => i === index),
                );
              }}
              onMouseLeave={() =>
                setHighlightedSourceLinkStates(filteredSources.map(() => false))
              }
              runId={runId}
            />
          </VStack>

          <Divider my={4} />  {/* separator between sources and "Answer" */}

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
          <>
            <HStack spacing={2}>
              <Button
                ref={upButtonRef}
                size="sm"
                variant="outline" /* istanbul ignore next */
                colorScheme={feedback === null ? "green" : "gray"}
                onClick={() => {
                  if (feedback === null && props.message.runId) {
                    setPendingScore(1);
                    setIsModalOpen(true);
                    setFeedbackColor("border-4 border-green-300");
                  } else {
                    /* istanbul ignore next */
                    toast.error("You have already provided your feedback.");
                  }
                }}
              >
                👍
              </Button>
              <Button
                ref={downButtonRef}
                size="sm"
                variant="outline" /* istanbul ignore next */
                colorScheme={feedback === null ? "red" : "gray"}
                onClick={() => {
                  if (feedback === null && props.message.runId) {
                    setPendingScore(0);
                    setIsModalOpen(true);
                    setFeedbackColor("border-4 border-red-300");
                  } else {
                    /* istanbul ignore next */
                    toast.error("You have already provided your feedback.");
                  }
                }}
              >
                👎
              </Button>
              <Spacer />
              <Button
                size="sm"
                variant="outline" /* istanbul ignore next */
                colorScheme={feedback === null ? "blue" : "gray"}
                onClick={() => {
                  if (feedback === null && props.message.runId) {
                    setPendingScore(null);
                    setIsModalOpen(true);
                    setFeedbackColor("border-4 border-blue-300");
                  } else {
                    /* istanbul ignore next */
                    toast.error("You have already provided your feedback.");
                  }
                }}

                color="black"
              >
                Submit Feedback
              </Button>
            </HStack>
            <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)}>
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Provide Feedback</ModalHeader>
                <ModalCloseButton />
                <ChakraModalBody>
                  <Textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="Enter your feedback"
                  />
                </ChakraModalBody>
                <ModalFooter>
                  <Button
                    colorScheme="blue"
                    mr={3}
                    onClick={async () => {
                      const key =
                        pendingScore === null ? "feedback_only" : "user_score";
                      await sendUserFeedback(pendingScore, key);
                      setIsModalOpen(false);
                    }}
                    isLoading={isLoading}
                  >
                    Send
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>
          </>
        )}

      {!isUser && <Divider mt={4} mb={4} />}
    </VStack>
  );
}
