import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { SessionProvider } from "next-auth/react";
import { ChatWindow } from "../ChatWindow";
import { fetchIndexOptions } from "../../utils/fetchIndexOptions";

jest.mock("../../utils/fetchIndexOptions", () => ({
  fetchIndexOptions: jest.fn(),
}));

beforeEach(() => {
  jest.clearAllMocks();
});

test("renders EmptyState when no messages", async () => {
  (fetchIndexOptions as jest.Mock).mockResolvedValue([]);

  const mockSession = {
    accessToken: "test-token",
  } as any;

  render(
    <SessionProvider session={mockSession}>
      <ChatWindow />
    </SessionProvider>,
  );

  await waitFor(() =>
    expect(screen.getByText("DRS ASSISTANT")).toBeInTheDocument(),
  );
});
import { fetchEventSource } from "@microsoft/fetch-event-source";

jest.mock("@microsoft/fetch-event-source", () => ({
  fetchEventSource: jest.fn(() => Promise.resolve()),
}));

test("shows options and sends initial question", async () => {
  (fetchIndexOptions as jest.Mock).mockResolvedValue([
    { name: "idx", display_name: "Index", example_questions: ["q1"] },
  ]);
  const mockSession = { accessToken: "token" } as any;
  render(
    <SessionProvider session={mockSession}>
      <ChatWindow />
    </SessionProvider>,
  );
  await screen.findByText("Select Document Index");
  const select = screen.getByRole("combobox");
  fireEvent.change(select, { target: { value: "idx" } });
  fireEvent.mouseUp(screen.getByText("q1"));
  expect(fetchEventSource).toHaveBeenCalled();
  expect(screen.queryByText("q1")).not.toBeNull();
});

test("send button disabled without index", async () => {
  (fetchIndexOptions as jest.Mock).mockResolvedValue([]);
  const mockSession = { accessToken: "token" } as any;
  render(
    <SessionProvider session={mockSession}>
      <ChatWindow />
    </SessionProvider>,
  );
  await screen.findByText("DRS ASSISTANT");
  expect(screen.getByLabelText("Send")).toBeDisabled();
});

test("does not send message when index not selected", async () => {
  (fetchIndexOptions as jest.Mock).mockResolvedValue([]);
  const mockSession = { accessToken: "token" } as any;
  render(
    <SessionProvider session={mockSession}>
      <ChatWindow />
    </SessionProvider>,
  );
  await screen.findByText("DRS ASSISTANT");
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "hello" } });
  fireEvent.click(screen.getByLabelText("Send"));
  expect(fetchEventSource).not.toHaveBeenCalled();
});

test("sends message and processes stream", async () => {
  (fetchIndexOptions as jest.Mock).mockResolvedValue([
    { name: "idx", display_name: "Index", example_questions: ["q"] },
  ]);
  (fetchEventSource as jest.Mock).mockImplementation(async (_url, opts) => {
    opts.onmessage?.({
      event: "data",
      data: JSON.stringify({ streamed_output: ["hi"], id: "1", ops: [] }),
    });
    opts.onmessage?.({ event: "end" });
  });
  const mockSession = { accessToken: "token" } as any;
  render(
    <SessionProvider session={mockSession}>
      <ChatWindow />
    </SessionProvider>,
  );
  await screen.findByText("Select Document Index");
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "idx" } });
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "hello" } });
  fireEvent.click(screen.getByLabelText("Send"));
  await waitFor(() => expect(fetchEventSource).toHaveBeenCalled());
  expect(screen.getByText(/hello/)).toBeInTheDocument();
});

test("changing index resets chat", async () => {
  (fetchIndexOptions as jest.Mock).mockResolvedValue([
    { name: "idx", display_name: "Index", example_questions: ["q"] },
    { name: "idx2", display_name: "Other", example_questions: ["q"] },
  ]);
  (fetchEventSource as jest.Mock).mockImplementation(async (_url, opts) => {
    opts.onmessage?.({
      event: "data",
      data: JSON.stringify({ streamed_output: ["hi"], id: "1", ops: [] }),
    });
    opts.onmessage?.({ event: "end" });
  });
  const mockSession = { accessToken: "token" } as any;
  render(
    <SessionProvider session={mockSession}>
      <ChatWindow />
    </SessionProvider>,
  );
  await screen.findByText("Select Document Index");
  const select = screen.getByRole("combobox");
  fireEvent.change(select, { target: { value: "idx" } });
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "hello" } });
  fireEvent.click(screen.getByLabelText("Send"));
  await waitFor(() => expect(fetchEventSource).toHaveBeenCalled());
  fireEvent.change(select, { target: { value: "idx2" } });
  await waitFor(() => expect(fetchEventSource).toHaveBeenCalled());
});
