import { render } from "@testing-library/react";
import { filterSources, createAnswerElements } from "../ChatMessageBubble";
import React from "react";

test("filters duplicate sources", () => {
  const sources = [
    { url: "a", title: "A" },
    { url: "a", title: "A2" },
    { url: "b", title: "B" },
  ];
  const { filtered, indexMap } = filterSources(sources as any);
  expect(filtered.length).toBe(2);
  expect(indexMap.get(1)).toBe(0);
});

test("creates citation elements", () => {
  const sources = [{ url: "a", title: "A" }];
  const { filtered, indexMap } = filterSources(sources as any);
  const res = createAnswerElements(
    "test [0]",
    filtered as any,
    indexMap,
    [false],
    jest.fn(),
  );
  const { container } = render(<>{res}</>);
  expect(container.querySelector("a")).toBeTruthy();
});
import { screen, fireEvent } from "@testing-library/react";
import { ChatMessageBubble } from "../ChatMessageBubble";
import { sendFeedback } from "../../utils/sendFeedback";
import { useSession } from "next-auth/react";

jest.mock("../../utils/sendFeedback");
jest.mock("next-auth/react");

beforeEach(() => {
  (useSession as jest.Mock).mockReturnValue({ data: { accessToken: "t" } });
});

test("renders user message", () => {
  render(
    <ChatMessageBubble
      message={{ id: "1", content: "hi", role: "user" }}
      isMostRecent={false}
      messageCompleted
    />,
  );
  expect(screen.getByText("hi")).toBeInTheDocument();
});

test("assistant feedback buttons trigger sendFeedback", () => {
  (sendFeedback as jest.Mock).mockResolvedValue({ code: 200, feedbackId: "f" });
  render(
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
  fireEvent.click(screen.getByText("👍"));
  expect(sendFeedback).toHaveBeenCalled();
});
