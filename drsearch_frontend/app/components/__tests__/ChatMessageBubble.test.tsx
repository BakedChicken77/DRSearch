// app/components/__tests__/ChatMessageBubble.test.tsx
import React from "react";
import {
  render,
  screen,
  fireEvent,
  waitFor
} from "@testing-library/react";
import {
  filterSources,
  createAnswerElements,
  ChatMessageBubble
} from "../ChatMessageBubble";
import { sendFeedback } from "../../utils/sendFeedback";
import { SessionProvider, useSession } from "next-auth/react";
import { ChakraProvider } from "@chakra-ui/react";

jest.mock("../../utils/sendFeedback");
jest.mock("next-auth/react");

const renderWithProviders = (ui: React.ReactElement) =>
  render(
    <ChakraProvider>
      <SessionProvider session={null}>{ui}</SessionProvider>
    </ChakraProvider>
  );

beforeEach(() => {
  (useSession as jest.Mock).mockReturnValue({
    data: { accessToken: "t" }
  });
});

describe("utility functions", () => {
  test("filters duplicate sources", () => {
    const sources = [
      { url: "a", title: "A" },
      { url: "a", title: "A2" },
      { url: "b", title: "B" }
    ];
    const { filtered, indexMap } = filterSources(sources as any);
    expect(filtered).toHaveLength(2);
    expect(indexMap.get(1)).toBe(0);
  });

  test("creates citation elements", () => {
    const sources = [{ url: "a", title: "A" }];
    const { filtered, indexMap } = filterSources(sources as any);
    const elements = createAnswerElements(
      "test [0]",
      filtered as any,
      indexMap,
      [false],
      jest.fn()
    );
    const { container } = render(<>{elements}</>);
    const link = container.querySelector("a");
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
      />
    );
    expect(container.innerHTML).toContain("hi");
  });

  test("assistant feedback button triggers sendFeedback", async () => {
    (sendFeedback as jest.Mock).mockResolvedValue({
      code: 200,
      feedbackId: "f"
    });

    renderWithProviders(
      <ChatMessageBubble
        message={{
          id: "2",
          content: "answer",
          role: "assistant",
          runId: "r",
          sources: []
        }}
        isMostRecent
        messageCompleted
      />
    );

    // first button is 👍
    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[0]);

    await waitFor(() => {
      expect(sendFeedback).toHaveBeenCalledTimes(1);
      expect(sendFeedback).toHaveBeenCalledWith(
        expect.objectContaining({
          score: 1,
          runId: "r",
          key: "user_score"
        })
      );
    });
  });
});
