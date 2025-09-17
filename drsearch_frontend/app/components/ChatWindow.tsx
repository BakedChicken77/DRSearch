// app\components\ChatWindow.tsx

"use client";

import React, { useRef, useState, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import { useSession } from "next-auth/react";
import { EmptyState } from "../components/EmptyState";
import { ChatMessageBubble, Message } from "../components/ChatMessageBubble";
import { AutoResizeTextarea } from "./AutoResizeTextarea";
import { marked, Renderer } from "marked";
import hljs from "highlight.js";
import "highlight.js/styles/gradient-dark.css";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { applyPatch } from "fast-json-patch";
import "react-toastify/dist/ReactToastify.css";
import { toast } from "react-toastify";
import {
  Heading,
  Flex,
  IconButton,
  InputGroup,
  InputRightElement,
  Spinner,
  Select,
} from "@chakra-ui/react";
import { ArrowUpIcon, AddIcon } from "@chakra-ui/icons";
import { Source } from "./SourceBubble";
import { SettingsDrawer } from "./SettingsDrawer";
import { apiBaseUrl } from "../utils/constants";
import { fetchIndexOptions, IndexOption } from "../utils/fetchIndexOptions";
import { Box } from "@chakra-ui/react";


import dynamic from "next/dynamic";
// @ts-ignore – typing is inferred
const RichAcronymEditor = dynamic(() => import("./RichAcronymEditor"), {
  ssr: false,
});

export function ChatWindow(props: {
  placeholder?: string;
  titleText?: string;
}) {
  // conversation/session identifiers
  const [conversationId, setConversationId] = useState<string>(uuidv4());
  const messageContainerRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  // chat state
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<
    { human: string; ai: string }[]
  >([]);

  const { placeholder, titleText = "DRS ASSISTANT" } = props;

  // index selection
  const [selectedIndexName, setSelectedIndexName] = useState("");
  const [acronymMap, setAcronymMap] = useState<Record<string, string>>({});

  // number of docs
  const [numDocs, setNumDocs] = useState(3);

  // fetched options
  const [indexOptions, setIndexOptions] = useState<IndexOption[] | null>(null);
  const [loadingOptions, setLoadingOptions] = useState(true);

  const handleIndexChange = (name: string) => {
    setSelectedIndexName(name);
    const opt = indexOptions?.find((o) => o.name === name);
    const raw = opt?.acronyms || {};
    const uppercased = Object.fromEntries(
      Object.entries(raw).map(([k, v]) => [k.toUpperCase(), v])
    );
    setAcronymMap(uppercased);
  };

  // reset on index change
  const prevIndexRef = useRef<string>("");
  useEffect(() => {
    if (prevIndexRef.current && prevIndexRef.current !== selectedIndexName) {
      setMessages([]);
      setChatHistory([]);
      setInput("");
      setConversationId(uuidv4());
    }
    prevIndexRef.current = selectedIndexName;
  }, [selectedIndexName]); // istanbul ignore next

  // **MOVED**: fetch dropdown options (was below the auth block)
  useEffect(() => {
    (async () => {
      try {
        const opts = await fetchIndexOptions(
          AUTH_ENABLED ? accessToken : undefined,
        );
        setIndexOptions(opts);
      } catch (e: any) {
        toast.error(e.message || "Unable to load index list");
        setIndexOptions([]);
      } finally {
        setLoadingOptions(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // istanbul ignore next

  // auth & session
  const AUTH_ENABLED = process.env.NEXT_PUBLIC_AUTH_ENABLED !== "False";
  const { data: session, status } = useSession();
  let accessToken = "";

  if (AUTH_ENABLED) {
    if (status === "loading") return <p>Loading...</p>; // istanbul ignore next
    if (!session) return <p>You are not authenticated. Please sign in.</p>; // istanbul ignore next
    accessToken = session.accessToken as string;
  } else {
    accessToken =
      process.env.NODE_ENV === "development"
        ? (process.env.NEXT_PUBLIC_DEV_ACCESS_TOKEN ?? "")
        : "";
  }

  // send a chat message
  const sendMessage = async (message?: string) => {
    if (!selectedIndexName) {
      /* istanbul ignore next */
      console.warn("No index selected, cannot send message");
      /* istanbul ignore next */
      return;
    }
    if (messageContainerRef.current) {
      messageContainerRef.current.classList.add("grow");
    }
    if (isLoading) return;

    const messageValue = message ?? input;
    if (!messageValue) return;

    setInput("");
    const parsedUser = marked.parse(messageValue);
    setMessages((m) => [
      ...m,
      { id: Math.random().toString(), content: parsedUser, role: "user" },
    ]);
    setIsLoading(true);

    let accumulated = "";
    let runId: string | undefined;
    let sources: Source[] | undefined;
    let msgIdx: number | null = null;

    // **THIS** is the persistent state for patching:
    let streamedResponse: any = {};

    // set up Markdown renderer
    const renderer = new Renderer();
    renderer.paragraph = (text) => text + "\n";
    renderer.list = (text) => `${text}\n\n`;
    renderer.listitem = (text) => `\n• ${text}`;
    renderer.code = (code, lang) => {
      /* istanbul ignore next */
      const valid = hljs.getLanguage(lang || "") ? lang : "plaintext";
      const highlighted = hljs.highlight(valid || "plaintext", code).value;
      return `<pre class="highlight bg-gray-700" style="padding:5px;border-radius:5px;overflow:auto;white-space:pre-wrap;line-height:1.2"><code class="${lang}" style="color:#d6e2ef;font-size:12px">${highlighted}</code></pre>`;
    };
    marked.setOptions({ renderer });

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    };
    if (AUTH_ENABLED) headers.Authorization = `Bearer ${accessToken}`;

    try {
      await fetchEventSource(`${apiBaseUrl}/chat/stream_log`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          input: {
            question: messageValue,
            chat_history: chatHistory,
            index_name: selectedIndexName,
            num_docs_retrieved: numDocs,
          },
          config: { metadata: { conversation_id: conversationId } },
          include_names: ["FindDocs"],
        }),
        openWhenHidden: true,
        onerror(err) {
          /* istanbul ignore next */
          console.error("Error in EventSource:", err);
          /* istanbul ignore next */
          throw err;
        },
        onmessage(msg) {
          if (msg.event === "end") {
            setChatHistory((h) => [
              ...h,
              { human: messageValue, ai: accumulated },
            ]);
            setIsLoading(false);
            return;
          }

          if (msg.event === "data" && msg.data) {
            const chunk = JSON.parse(msg.data);

            // ═ Apply patches to our persistent object ═
            streamedResponse = applyPatch(
              streamedResponse,
              chunk.ops,
            ).newDocument;

            const doc = streamedResponse;

            // extract sources if present
            if (Array.isArray(doc.logs?.FindDocs?.final_output?.output)) {
              sources = doc.logs.FindDocs.final_output.output.map((d: any) => ({
                url: d.metadata.file_path,
                title: d.metadata.filename,
              }));
            }

            // track run ID
            if (doc.id) runId = doc.id;

            // accumulate streamed text
            if (Array.isArray(doc.streamed_output)) {
              accumulated = doc.streamed_output.join("");
            }

            const rendered = marked.parse(accumulated);

            // update assistant bubble
            setMessages((prev) => {
              const copy = [...prev];
              if (msgIdx === null || !copy[msgIdx]) {
                msgIdx = copy.length;
                copy.push({
                  id: Math.random().toString(),
                  content: rendered.trim(),
                  runId,
                  sources,
                  role: "assistant",
                });
              } else {
                copy[msgIdx].content = rendered.trim();
                copy[msgIdx].runId = runId;
                copy[msgIdx].sources = sources;
              }
              return copy;
            });
          }
        },
      });
    } catch (e: any) {
      /* istanbul ignore next */
      console.error("Send message error:", e);
      /* istanbul ignore next */
      setMessages((prev) => prev.slice(0, -1));
      /* istanbul ignore next */
      setIsLoading(false);
      /* istanbul ignore next */
      setInput(messageValue);
      /* istanbul ignore next */
      throw e;
    }
  };

  // initial question helper
  const sendInitialQuestion = (q: string) => sendMessage(q);

  // reset chat while keeping index and settings
  const handleNewChat = () => {
    setMessages([]);
    setChatHistory([]);
    setInput("");
    setConversationId(uuidv4());
    if (messageContainerRef.current) {
      messageContainerRef.current.classList.remove("grow");
    }
  };

  return (
    <div className="flex flex-col items-center p-8 rounded grow max-h-full">
      <SettingsDrawer numDocs={numDocs} setNumDocs={setNumDocs} />
      <IconButton
        aria-label="start new chat"
        title="start new chat"
        icon={<AddIcon boxSize={6} />}
        position="absolute"
        top={14}
        left={2}
        onClick={handleNewChat}
      />
      {messages.length > 0 ? (
        <Flex direction="column" alignItems="center" pb="20px">
          <Heading fontSize="8xl" fontWeight="medium" mb={1} color="black">
            {titleText}
          </Heading>
          <Heading fontSize="md" fontWeight="normal" mb={1} color="black">
            Your DRS Assistant
          </Heading>

          {/* dropdown from backend */}
          <Select
            data-testid="index-select"
            value={selectedIndexName}
            onChange={(e) => handleIndexChange(e.target.value)}
            placeholder="Select Document Index"
            mb="20px"
            width="auto"
            isDisabled={loadingOptions || (indexOptions?.length ?? 0) === 0}
          >
            {indexOptions?.map((opt) => (
              <option
                key={opt.name}
                value={opt.name}
                disabled={!opt.initialized}
                className={!opt.initialized ? "text-gray-400" : ""}
              >
                {opt.display_name}
              </option>
            ))}
          </Select>
        </Flex>
      ) : (
        <EmptyState
          onChoice={sendInitialQuestion}
          selectedIndexName={selectedIndexName}
          onIndexChange={handleIndexChange}
          indexOptions={indexOptions}
          loadingOptions={loadingOptions}
        />
      )}

      {/* message list */}
      <div
        className="flex flex-col-reverse w-full mb-2 overflow-auto"
        ref={messageContainerRef}
        data-testid="chat-stream"
      >
        {messages.length > 0 &&
          [...messages]
            .reverse()
            .map((m, i) => (
              <ChatMessageBubble
                key={m.id}
                message={{ ...m }}
                aiEmoji="🦜"
                isMostRecent={i === 0}
                messageCompleted={!isLoading}
                conversation={messages}
              />
            ))}
      </div>

      {/* input + send */}
      <InputGroup size="md" alignItems="center">
        <Box flex="1" mr="56px">
          <RichAcronymEditor
            value={input}
            onChange={setInput}
            acronymMap={acronymMap}
            isDisabled={!selectedIndexName}
            placeholder={placeholder}
            onSubmit={(text) => {
              if (selectedIndexName) sendMessage(text);
            }}
          />
        </Box>
        <InputRightElement h="full">
          <IconButton
            data-testid="chat-send-btn"
            colorScheme="blue"
            rounded="full"
            aria-label="Send"
            icon={isLoading ? <Spinner /> : <ArrowUpIcon />}
            isDisabled={!selectedIndexName}
            _disabled={{
              backgroundColor: "gray.200",
              cursor: "not-allowed",
            }} /* istanbul ignore next */
            onClick={(e) => {
              e.preventDefault();
              sendMessage();
            }}
          />
        </InputRightElement>
      </InputGroup>

      {/* footer */}
      {messages.length === 0 && (
        <footer className="flex justify-center absolute bottom-8">
          <a
            href="https://www.leonardodrs.com/locations/airborne-intelligence-systems-fort-walton-beach/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-black flex items-center"
          >
            View AIS‑FWB Home Page
          </a>
        </footer>
      )}
    </div>
  );
}
