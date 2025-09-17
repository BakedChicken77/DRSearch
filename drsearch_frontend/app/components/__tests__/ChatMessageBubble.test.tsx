// app/components/__tests__/ChatMessageBubble.test.tsx
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { act } from "react-dom/test-utils";
import {
  filterSources,
  filterSourcesByCitations,
  createAnswerElements,
  ChatMessageBubble,
  __TEST__,
} from "../ChatMessageBubble";
import { sendFeedback } from "../../utils/sendFeedback";
import { SessionProvider, useSession } from "next-auth/react";
import { ChakraProvider } from "@chakra-ui/react";
import { emojisplosion } from "emojisplosion";

jest.mock("emojisplosion", () => ({ emojisplosion: jest.fn() }));

jest.mock("../../utils/sendFeedback");
jest.mock("next-auth/react", () => ({
  __esModule: true,
  SessionProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useSession: jest.fn(),
}));

const renderWithProviders = (ui: React.ReactElement) =>
  render(
    <ChakraProvider>
      <SessionProvider session={null}>{ui}</SessionProvider>
    </ChakraProvider>,
  );

const createDeferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

let consoleLogSpy: jest.SpyInstance;
let consoleWarnSpy: jest.SpyInstance;
let consoleErrorSpy: jest.SpyInstance;
let consoleDebugSpy: jest.SpyInstance;

beforeEach(() => {
  (useSession as jest.Mock).mockReturnValue({
    data: { accessToken: "t" },
  });
  consoleLogSpy = jest.spyOn(console, "log").mockImplementation(() => {});
  consoleWarnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
  consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
  consoleDebugSpy = jest.spyOn(console, "debug").mockImplementation(() => {});
});

afterEach(() => {
  jest.useRealTimers();
  consoleLogSpy.mockRestore();
  consoleWarnSpy.mockRestore();
  consoleErrorSpy.mockRestore();
  consoleDebugSpy.mockRestore();
  jest.clearAllMocks();
  __TEST__.sendUserFeedback = null;
  __TEST__.animateButton = null;
  __TEST__.setComment = null;
  __TEST__.comment = "";
});

describe("utility helpers", () => {
  test("filterSources deduplicates urls and builds source index map", () => {
    const sources = [
      { url: "a", title: "A" },
      { url: "a", title: "A2" },
      { url: "b", title: "B" },
      { url: "c", title: "C" },
    ];

    const { filtered, indexMap } = filterSources(sources as any);

    expect(filtered).toHaveLength(3);
    expect(filtered.map((s) => s.title)).toEqual(["A", "B", "C"]);
    expect(indexMap.get(0)).toBe(0);
    expect(indexMap.get(1)).toBe(0);
    expect(indexMap.get(2)).toBe(1);
    expect(indexMap.get(3)).toBe(2);
  });

  test("filterSources warns when url missing", () => {
    const sources = [{ title: "Missing" }];

    const { filtered } = filterSources(sources as any);

    expect(filtered).toHaveLength(0);
    expect(consoleWarnSpy).toHaveBeenCalledWith(
      "Source at index 0 has undefined url and will be skipped.",
    );
  });

  test("filterSourcesByCitations retains only referenced deduped sources", () => {
    const sources = [
      { url: "url1", title: "Doc 1" },
      { url: "url1", title: "Doc 1 duplicate" },
      { url: "url2", title: "Doc 2" },
    ];
    const { filtered, indexMap } = filterSources(sources as any);

    const { filteredSources, indexMap: filteredMap } = filterSourcesByCitations(
      "Only referencing [1]",
      filtered,
      indexMap,
    );

    expect(filteredSources).toHaveLength(1);
    expect(filteredSources[0].title).toBe("Doc 1");
    expect(filteredMap.get(0)).toBe(0);
    expect(filteredMap.get(1)).toBe(0);
    expect(filteredMap.has(2)).toBe(false);
  });

  test("createAnswerElements renders citations with deduped numbering", async () => {
    const sources = [
      { url: "u1", title: "Doc 1" },
      { url: "u1", title: "Doc 1 duplicate" },
      { url: "u2", title: "Doc 2" },
    ];
    const { filtered, indexMap } = filterSources(sources as any);
    const highlightStates = new Array(filtered.length).fill(false);
    const setHighlight = jest.fn();

    const elements = createAnswerElements(
      "One [0] two [1] three [2]",
      filtered as any,
      indexMap,
      highlightStates,
      setHighlight,
    );

    const { container } = render(<>{elements}</>);
    const anchors = container.querySelectorAll("a");
    expect(anchors).toHaveLength(3);

    expect(anchors[0].textContent).toBe("1");
    expect(anchors[0]).toHaveAttribute("href", "u1");
    expect(anchors[1].textContent).toBe("1");
    expect(anchors[1]).toHaveAttribute("href", "u1");
    expect(anchors[2].textContent).toBe("2");
    expect(anchors[2]).toHaveAttribute("href", "u2");

    const user = userEvent.setup();
    await user.hover(anchors[0]);
    expect(setHighlight).toHaveBeenLastCalledWith([true, false]);
    await user.unhover(anchors[0]);
    expect(setHighlight).toHaveBeenLastCalledWith([false, false]);
  });

  test("createAnswerElements falls back to last source for unknown citation", () => {
    const sources = Array.from({ length: 11 }, (_, i) => ({
      url: `u${i}`,
      title: `t${i}`,
    }));
    const elements = createAnswerElements(
      "hi [5] there",
      sources as any,
      new Map(),
      new Array(11).fill(false),
      jest.fn(),
    );
    const { container } = render(<>{elements}</>);
    const link = container.querySelector("a")!;
    expect(link).toHaveAttribute("href", "u10");
    expect(link.textContent).toBe("6");
  });
});

describe("ChatMessageBubble", () => {
  test("renders user message content", () => {
    const { container } = renderWithProviders(
      <ChatMessageBubble
        message={{ id: "1", content: "hello", role: "user" }}
        isMostRecent={false}
        messageCompleted
        conversation={[]}
      />,
    );

    expect(container).toHaveTextContent("hello");
  });

  test("renders assistant message with deduped citations", () => {
    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "2",
          content: "See [0] and [1] and [2] and [3]",
          role: "assistant",
          runId: "run",
          sources: [
            { url: "url1", title: "Document 1" },
            { url: "url1", title: "Document 1 Duplicate" },
            { url: "url2", title: "Document 2" },
            { url: "url3", title: "Document 3" },
          ],
        }}
        isMostRecent
        messageCompleted
        conversation={[]}
      />,
    );

    expect(screen.getByText("View Sources")).toBeInTheDocument();
    const sourceEntries = screen.getAllByText(/Document/);
    expect(sourceEntries).toHaveLength(3);

    const citationLinks = screen.getAllByRole("link", { name: /\d/ });
    expect(citationLinks.map((link) => link.textContent)).toEqual([
      "1",
      "1",
      "2",
      "3",
    ]);
    expect(citationLinks[0]).toHaveAttribute("href", "url1");
    expect(citationLinks[1]).toHaveAttribute("href", "url1");
    expect(citationLinks[2]).toHaveAttribute("href", "url2");
    expect(citationLinks[3]).toHaveAttribute("href", "url3");
  });

  test("hovering citations syncs highlight state", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "hover",
          content: "answer [0]",
          role: "assistant",
          runId: "run",
          sources: [{ url: "u", title: "Title" }],
        }}
        isMostRecent
        messageCompleted
        conversation={[]}
      />,
    );

    const citation = screen.getByRole("link", { name: "1" });
    const source = screen.getByText("Title");

    await user.hover(citation);
    await waitFor(() => expect(source).toHaveClass("is-highlighted"));
    await user.unhover(citation);
    await waitFor(() => expect(source).not.toHaveClass("is-highlighted"));
  });

  test("hovering source list item highlights citations", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "hover2",
          content: "answer [0]",
          role: "assistant",
          runId: "run",
          sources: [{ url: "u", title: "Title" }],
        }}
        isMostRecent
        messageCompleted
        conversation={[]}
      />,
    );

    const citation = screen.getByRole("link", { name: "1" });
    const source = screen.getByText("Title");

    await user.hover(source);
    await waitFor(() =>
      expect(citation).toHaveClass("bg-[rgb(200, 1, 24)]"),
    );
    await user.unhover(source);
    await waitFor(() =>
      expect(citation).toHaveClass("bg-[rgb(228, 1, 44)]"),
    );
  });

  test("submits positive feedback and resets comment", async () => {
    const user = userEvent.setup();
    (sendFeedback as jest.Mock).mockResolvedValue({
      code: 200,
      feedbackId: "f",
    });

    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "p",
          content: "answer [0]",
          role: "assistant",
          runId: "run",
          sources: [{ url: "http://doc", title: "Doc" }],
        }}
        isMostRecent
        messageCompleted
        conversation={[
          { id: "1", content: "question", role: "user" } as any,
          {
            id: "p",
            content: "answer [0]",
            role: "assistant",
            runId: "run",
            sources: [{ url: "http://doc", title: "Doc" }],
          } as any,
        ]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "👍" }));
    const textarea = await screen.findByPlaceholderText("Enter your feedback");
    await user.type(textarea, "Great job");
    const sendButton = await screen.findByRole("button", { name: /send/i });
    (emojisplosion as jest.Mock).mockClear();
    await user.click(sendButton);

    await waitFor(() => {
      expect(sendFeedback).toHaveBeenCalledWith(
        expect.objectContaining({
          score: 1,
          runId: "run",
          key: "user_score",
          comment: "Great job",
          documents: ["http://doc"],
          conversation: [
            { role: "user", content: "question" },
            { role: "assistant", content: "answer [0]" },
          ],
          accessToken: "t",
        }),
      );
    });

    expect(emojisplosion).toHaveBeenCalledWith(
      expect.objectContaining({ emojis: ["👍"] }),
    );
    await waitFor(() => expect(__TEST__.comment).toBe(""));
  });

  test("submits negative feedback with animation", async () => {
    const user = userEvent.setup();
    (sendFeedback as jest.Mock).mockResolvedValue({
      code: 200,
      feedbackId: "d",
    });

    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "n",
          content: "answer",
          role: "assistant",
          runId: "run",
          sources: [],
        }}
        isMostRecent
        messageCompleted
        conversation={[]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "👎" }));
    const textarea = await screen.findByPlaceholderText("Enter your feedback");
    await user.type(textarea, "Needs work");
    const sendButton = await screen.findByRole("button", { name: /send/i });
    (emojisplosion as jest.Mock).mockClear();
    await user.click(sendButton);

    await waitFor(() =>
      expect(sendFeedback).toHaveBeenCalledWith(
        expect.objectContaining({
          score: 0,
          key: "user_score",
        }),
      ),
    );
    expect(emojisplosion).toHaveBeenCalledWith(
      expect.objectContaining({ emojis: ["👎"] }),
    );
  });

  test("submits feedback without score", async () => {
    const user = userEvent.setup();
    (sendFeedback as jest.Mock).mockResolvedValue({
      code: 200,
      feedbackId: "c",
    });

    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "s",
          content: "answer",
          role: "assistant",
          runId: "run",
          sources: [{ url: "u", title: "Title" }],
        }}
        isMostRecent
        messageCompleted
        conversation={[]}
      />,
    );

    await user.click(screen.getByRole("button", { name: /submit feedback/i }));
    const textarea = await screen.findByPlaceholderText("Enter your feedback");
    await user.type(textarea, "General note");
    const sendButton = await screen.findByRole("button", { name: /send/i });
    (emojisplosion as jest.Mock).mockClear();
    await user.click(sendButton);

    await waitFor(() =>
      expect(sendFeedback).toHaveBeenCalledWith(
        expect.objectContaining({
          score: undefined,
          key: "feedback_only",
          comment: "General note",
        }),
      ),
    );
    expect(emojisplosion).not.toHaveBeenCalled();
  });

  test("warns when run id missing", async () => {
    renderWithProviders(
      <ChatMessageBubble
        message={{ id: "no-run", content: "answer", role: "assistant" }}
        isMostRecent
        messageCompleted
        conversation={[]}
      />,
    );

    await act(async () => {
      await __TEST__.sendUserFeedback?.(1, "user_score");
    });

    expect(consoleWarnSpy).toHaveBeenCalledWith(
      "Run ID is undefined, cannot send feedback",
    );
    expect(sendFeedback).not.toHaveBeenCalled();
  });

  test("warns when already loading feedback", async () => {
    const deferred = createDeferred<{ code: number; feedbackId: string }>();
    (sendFeedback as jest.Mock).mockReturnValue(deferred.promise);

    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "loading",
          content: "answer",
          role: "assistant",
          runId: "run",
          sources: [],
        }}
        isMostRecent
        messageCompleted
        conversation={[]}
      />,
    );

    await act(async () => {
      void __TEST__.sendUserFeedback?.(1, "user_score");
      await Promise.resolve();
    });

    expect(sendFeedback).toHaveBeenCalledTimes(1);

    await act(async () => {
      await __TEST__.sendUserFeedback?.(1, "user_score");
    });

    expect(consoleWarnSpy).toHaveBeenCalledWith(
      "Already loading, cannot send feedback",
    );

    await act(async () => {
      deferred.resolve({ code: 200, feedbackId: "id" });
    });
  });

  test("handles feedback errors", async () => {
    const user = userEvent.setup();
    const error = new Error("boom");
    (sendFeedback as jest.Mock).mockRejectedValue(error);
    const toast = require("react-toastify").toast;
    const toastSpy = jest
      .spyOn(toast, "error")
      .mockImplementation(() => {});

    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "err",
          content: "answer",
          role: "assistant",
          runId: "run",
          sources: [],
        }}
        isMostRecent
        messageCompleted
        conversation={[]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "👍" }));
    const textarea = await screen.findByPlaceholderText("Enter your feedback");
    await user.type(textarea, "Oops");
    await user.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(toastSpy).toHaveBeenCalledWith("boom"));
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      "Error sending feedback:",
      error,
    );
    toastSpy.mockRestore();
  });

  test("prevents feedback after submission", async () => {
    const user = userEvent.setup();
    (sendFeedback as jest.Mock).mockResolvedValue({
      code: 200,
      feedbackId: "done",
    });
    const toast = require("react-toastify").toast;
    const toastSpy = jest
      .spyOn(toast, "error")
      .mockImplementation(() => {});

    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "post",
          content: "answer",
          role: "assistant",
          runId: "run",
          sources: [],
        }}
        isMostRecent
        messageCompleted
        conversation={[]}
      />,
    );

    const upvote = screen.getByRole("button", { name: "👍" });
    await user.click(upvote);
    await user.click(await screen.findByRole("button", { name: /send/i }));
    await waitFor(() => expect(sendFeedback).toHaveBeenCalledTimes(1));

    await user.click(upvote);
    expect(toastSpy).toHaveBeenCalledWith(
      "You have already provided your feedback.",
    );

    await user.click(screen.getByRole("button", { name: /submit feedback/i }));
    expect(toastSpy).toHaveBeenCalledWith(
      "You have already provided your feedback.",
    );
    toastSpy.mockRestore();
  });

  test("does not show sources when content lacks citations", () => {
    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "no-cite",
          content: "answer",
          role: "assistant",
          runId: "run",
          sources: [{ url: "u", title: "Title" }],
        }}
        isMostRecent
        messageCompleted
        conversation={[]}
      />,
    );

    expect(screen.queryByText("View Sources")).not.toBeInTheDocument();
  });

  test("animateButton gracefully ignores unknown id", () => {
    renderWithProviders(
      <ChatMessageBubble
        message={{ id: "anim", content: "answer", role: "assistant", runId: "run" }}
        isMostRecent
        messageCompleted
        conversation={[]}
      />,
    );

    __TEST__.animateButton?.("unknown");
    expect(emojisplosion).not.toHaveBeenCalled();
  });

  test("animateButton triggers emojisplosion for up and down buttons", () => {
    jest.useFakeTimers();

    renderWithProviders(
      <ChatMessageBubble
        message={{ id: "anim2", content: "answer", role: "assistant", runId: "run" }}
        isMostRecent
        messageCompleted
        conversation={[]}
      />,
    );

    const upButton = screen.getByRole("button", { name: "👍" });
    Object.defineProperty(upButton, "offsetTop", {
      value: 10,
      configurable: true,
    });
    Object.defineProperty(upButton, "offsetLeft", {
      value: 20,
      configurable: true,
    });
    Object.defineProperty(upButton, "clientWidth", {
      value: 100,
      configurable: true,
    });
    Object.defineProperty(upButton, "clientHeight", {
      value: 40,
      configurable: true,
    });

    (emojisplosion as jest.Mock).mockClear();
    act(() => {
      __TEST__.animateButton?.("upButton");
    });
    const upArgs = (emojisplosion as jest.Mock).mock.calls[0][0];
    expect(upArgs.emojis).toEqual(["👍"]);
    expect(upArgs.position()).toEqual({ x: 70, y: 30 });

    (emojisplosion as jest.Mock).mockClear();
    act(() => {
      __TEST__.animateButton?.("downButton");
    });
    const downArgs = (emojisplosion as jest.Mock).mock.calls[0][0];
    expect(downArgs.emojis).toEqual(["👎"]);
    expect(downArgs.position()).toEqual({ x: 0, y: 0 });

    jest.runAllTimers();
  });
});
