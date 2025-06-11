import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SourceList } from "../SourceList";
import { sendFeedback } from "../../utils/sendFeedback";
import { SessionProvider, useSession } from "next-auth/react";

jest.mock("../../utils/sendFeedback");
jest.mock("next-auth/react", () => ({
  __esModule: true,
  SessionProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useSession: jest.fn(),
}));

const sources = [{ url: "http://example.com", title: "Example" }];

beforeEach(() => {
  (useSession as jest.Mock).mockReturnValue({ data: { accessToken: "t" } });
});

const renderWithSession = (ui: React.ReactElement) =>
  render(<SessionProvider session={null}>{ui}</SessionProvider>);

it("renders source title", () => {
  renderWithSession(
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
  renderWithSession(
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
      accessToken: "t",
    }),
  );
});
