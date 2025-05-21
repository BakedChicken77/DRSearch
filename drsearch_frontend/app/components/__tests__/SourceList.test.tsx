import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SourceList } from "../SourceList";
import { sendFeedback } from "../../utils/sendFeedback";

jest.mock("../../utils/sendFeedback");

const sources = [{ url: "http://example.com", title: "Example" }];

it("renders source title", () => {
  render(
    <SourceList
      sources={sources}
      highlightedStates={[false]}
      onMouseEnter={() => {}}
      onMouseLeave={() => {}}
    />,
  );
  expect(screen.getByText("Example")).toBeInTheDocument();
});

it("handles hover and click", async () => {
  const enter = jest.fn();
  const leave = jest.fn();
  (sendFeedback as jest.Mock).mockResolvedValue({});
  render(
    <SourceList
      sources={sources}
      highlightedStates={[false]}
      onMouseEnter={enter}
      onMouseLeave={leave}
      runId="r"
    />,
  );
  const link = screen.getByText("Example");
  fireEvent.mouseEnter(link);
  fireEvent.mouseLeave(link);
  expect(enter).toHaveBeenCalledWith(0);
  expect(leave).toHaveBeenCalled();
  fireEvent.click(link);
  await waitFor(() =>
    expect(sendFeedback).toHaveBeenCalledWith({
      key: "user_click",
      runId: "r",
      value: sources[0].url,
      isExplicit: false,
    }),
  );
});
