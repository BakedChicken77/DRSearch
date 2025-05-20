import { render, screen, fireEvent } from "@testing-library/react";
import { SourceBubble } from "../SourceBubble";
import { sendFeedback } from "../../utils/sendFeedback";

jest.mock("../../utils/sendFeedback");

const source = { url: "http://example.com", title: "Example" };

test("renders title", () => {
  render(
    <SourceBubble
      source={source}
      highlighted={false}
      onMouseEnter={() => {}}
      onMouseLeave={() => {}}
    />,
  );
  expect(screen.getByText("Example")).toBeInTheDocument();
});

test("calls handlers on hover", () => {
  const enter = jest.fn();
  const leave = jest.fn();
  render(
    <SourceBubble
      source={source}
      highlighted={false}
      onMouseEnter={enter}
      onMouseLeave={leave}
    />,
  );
  const card = screen.getByText("Example").closest("div") as HTMLElement;
  fireEvent.mouseEnter(card!);
  fireEvent.mouseLeave(card!);
  expect(enter).toHaveBeenCalled();
  expect(leave).toHaveBeenCalled();
});

test("sends feedback on click", async () => {
  (sendFeedback as jest.Mock).mockResolvedValue({});
  render(
    <SourceBubble
      source={source}
      highlighted={false}
      onMouseEnter={() => {}}
      onMouseLeave={() => {}}
      runId="123"
    />,
  );
  const card = screen.getByText("Example").closest("div") as HTMLElement;
  fireEvent.click(card!);
  expect(sendFeedback).toHaveBeenCalledWith({
    key: "user_click",
    runId: "123",
    value: source.url,
    isExplicit: false,
  });
});
