import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SourceBubble } from "../SourceBubble";
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

const source = { url: "http://example.com", title: "Example" };

const renderWithSession = (ui: React.ReactElement) =>
  render(<SessionProvider session={null}>{ui}</SessionProvider>);

beforeEach(() => {
  (useSession as jest.Mock).mockReturnValue({ data: { accessToken: "t" } });
});

test("renders title", () => {
  renderWithSession(
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
  renderWithSession(
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
  renderWithSession(
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
    accessToken: "t",
  });
});

test("logs opened url after click", async () => {
  (sendFeedback as jest.Mock).mockResolvedValue({});
  const logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
  renderWithSession(
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
  await waitFor(() => {
    expect(logSpy).toHaveBeenCalledWith("Opened file URL:", source.url);
  });
  logSpy.mockRestore();
});
