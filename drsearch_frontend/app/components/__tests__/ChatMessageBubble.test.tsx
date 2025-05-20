// app/components/__tests__/ChatMessageBubble.test.tsx
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  filterSources,
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
  // preserve actual named export SessionProvider but ensure it renders children
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

beforeEach(() => {
  (useSession as jest.Mock).mockReturnValue({
    data: { accessToken: "t" },
  });
  jest.clearAllMocks();
});

describe("utility functions", () => {
  test("filters duplicate sources", () => {
    const sources = [
      { url: "a", title: "A" },
      { url: "a", title: "A2" },
      { url: "b", title: "B" },
    ];
    const { filtered, indexMap } = filterSources(sources as any);
    expect(filtered).toHaveLength(2);
    expect(indexMap.get(1)).toBe(0);
  });

  test("handles sources without url", () => {
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    const sources = [{ title: "A" } as any];
    const { filtered } = filterSources(sources);
    expect(filtered).toHaveLength(0);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  test("creates citation elements", () => {
    const sources = [{ url: "a", title: "A" }];
    const { filtered, indexMap } = filterSources(sources as any);
    const setHighlight = jest.fn();
    const elements = createAnswerElements(
      "test [0]",
      filtered as any,
      indexMap,
      [false],
      setHighlight,
    );
    const { container } = render(<>{elements}</>);
    const link = container.querySelector("a")!;
    fireEvent.mouseEnter(link);
    expect(setHighlight).toHaveBeenCalledWith([true]);
    fireEvent.mouseLeave(link);
    expect(setHighlight).toHaveBeenCalledWith([false]);
    expect(link).toHaveAttribute("href", "a");
  });
});

describe("ChatMessageBubble component", () => {
  test("renders user message", () => {
    const { container } = renderWithProviders(
      <ChatMessageBubble
        message={{ id: "1", content: "hi", role: "user" }}
        isMostRecent={false}
        messageCompleted
      />,
    );
    expect(container.innerHTML).toContain("hi");
  });

  test("assistant feedback button triggers sendFeedback", async () => {
    jest.useFakeTimers();
    (sendFeedback as jest.Mock).mockResolvedValue({
      code: 200,
      feedbackId: "f",
    });

    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "2",
          content: "answer",
          role: "assistant",
          runId: "r",
          sources: [],
        }}
        isMostRecent
        messageCompleted
      />,
    );

    // first button is 👍
    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[0]);
    jest.runAllTimers();

    await waitFor(() => {
      expect(sendFeedback).toHaveBeenCalledTimes(1);
      expect(sendFeedback).toHaveBeenCalledWith(
        expect.objectContaining({
          score: 1,
          runId: "r",
          key: "user_score",
        }),
      );
    });
  });

  test("downvote button also sends feedback", async () => {
    (sendFeedback as jest.Mock).mockResolvedValue({
      code: 200,
      feedbackId: "d",
    });
    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "x",
          content: "a",
          role: "assistant",
          runId: "r",
          sources: [],
        }}
        isMostRecent
        messageCompleted
      />,
    );
    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[1]);
    await waitFor(() => expect(sendFeedback).toHaveBeenCalled());
  });

  test("does not send feedback when runId missing", () => {
    renderWithProviders(
      <ChatMessageBubble
        message={{ id: "3", content: "hi", role: "assistant" }}
        isMostRecent
        messageCompleted
      />,
    );
    fireEvent.click(screen.getAllByRole("button")[0]);
    expect(sendFeedback).not.toHaveBeenCalled();
  });

  test("ignores additional clicks while loading", async () => {
    let resolve: (v: any) => void = () => {};
    (sendFeedback as jest.Mock).mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );
    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "4",
          content: "answer",
          role: "assistant",
          runId: "r",
          sources: [],
        }}
        isMostRecent
        messageCompleted
      />,
    );
    const btn = screen.getAllByRole("button")[0];
    fireEvent.click(btn);
    fireEvent.click(btn);
    resolve({ code: 200, feedbackId: "ff" });
    await waitFor(() => expect(sendFeedback).toHaveBeenCalledTimes(1));
  });

  test("view trace button opens url", async () => {
    (global as any).fetch = jest.fn(() =>
      Promise.resolve({ json: () => Promise.resolve('"http://x"') }),
    );
    const open = (window.open = jest.fn());
    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "5",
          content: "answer",
          role: "assistant",
          runId: "r",
          sources: [],
        }}
        isMostRecent
        messageCompleted
      />,
    );
    fireEvent.click(screen.getByText(/view trace/i));
    await waitFor(() => expect(open).toHaveBeenCalled());
  });

  test("view trace shows error", async () => {
    (global as any).fetch = jest.fn(() =>
      Promise.resolve({ json: () => Promise.resolve({ code: 400 }) }),
    );
    const open = (window.open = jest.fn());
    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "6",
          content: "answer",
          role: "assistant",
          runId: "r",
          sources: [],
        }}
        isMostRecent
        messageCompleted
      />,
    );
    fireEvent.click(screen.getByText(/view trace/i));
    await waitFor(() => expect(open).not.toHaveBeenCalled());
  });

  test("source bubble hover highlights", () => {
    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "7",
          content: "answer",
          role: "assistant",
          runId: "r",
          sources: [{ url: "u", title: "Title" }],
        }}
        isMostRecent
        messageCompleted
      />,
    );
    const bubble = screen.getByText("Title");
    fireEvent.mouseEnter(bubble);
    fireEvent.mouseLeave(bubble);
  });

  test("citation fallback uses last source", () => {
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

  test("sendUserFeedback early returns", async () => {
    renderWithProviders(
      <ChatMessageBubble
        message={{ id: "e", content: "a", role: "assistant" }}
        isMostRecent
        messageCompleted
      />,
    );
    await (__TEST__.sendUserFeedback as any)(1, "user_score");
    expect(sendFeedback).not.toHaveBeenCalled();
  });

  test("comment resets after feedback", async () => {
    (sendFeedback as jest.Mock).mockResolvedValue({
      code: 200,
      feedbackId: "f",
    });
    renderWithProviders(
      <ChatMessageBubble
        message={{ id: "c", content: "a", role: "assistant", runId: "r" }}
        isMostRecent
        messageCompleted
      />,
    );
    (__TEST__.setComment as any)("note");
    await (__TEST__.sendUserFeedback as any)(1, "user_score");
    await waitFor(() => expect(__TEST__.comment).toBe(""));
  });

  test("animateButton default branch", () => {
    renderWithProviders(
      <ChatMessageBubble
        message={{ id: "b", content: "a", role: "assistant", runId: "r" }}
        isMostRecent
        messageCompleted
      />,
    );
    (__TEST__.animateButton as any)("unknown");
    expect(emojisplosion).not.toHaveBeenCalled();
  });

  test("post feedback clicks and trace error flow", async () => {
    jest.useRealTimers();
    (sendFeedback as jest.Mock).mockResolvedValue({
      code: 200,
      feedbackId: "1",
    });
    (global as any).fetch = jest.fn(() =>
      Promise.resolve({ json: () => Promise.resolve({ code: 400 }) }),
    );
    const toast = require("react-toastify").toast;
    const err = jest.spyOn(toast, "error").mockImplementation(() => {});
    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "z",
          content: "a",
          role: "assistant",
          runId: "r",
          sources: [],
        }}
        isMostRecent
        messageCompleted
      />,
    );
    const [up] = screen.getAllByRole("button");
    fireEvent.click(up);
    await waitFor(() => expect(sendFeedback).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 0));
    fireEvent.click(up);
    expect(err).toHaveBeenCalledWith(
      "You have already provided your feedback.",
    );
    await (__TEST__.viewTrace as any)();
    await waitFor(() =>
      expect(err).toHaveBeenCalledWith("Unable to view trace"),
    );
    err.mockRestore();
  });
});
