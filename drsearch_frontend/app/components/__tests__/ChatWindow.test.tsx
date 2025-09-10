import React from "react";
import {
  render,
  screen,
  waitFor,
  fireEvent,
  act,
} from "@testing-library/react";
import { SessionProvider, useSession } from "next-auth/react";
import { ChatWindow } from "../ChatWindow";
import { fetchIndexOptions } from "../../utils/fetchIndexOptions";
import hljs from "highlight.js";

jest.mock("../../utils/fetchIndexOptions", () => ({
  fetchIndexOptions: jest.fn(),
}));

jest.mock("next-auth/react", () => ({
  __esModule: true,
  SessionProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useSession: jest.fn(),
}));

beforeEach(() => {
  (useSession as jest.Mock).mockReturnValue({
    data: { accessToken: "token" },
    status: "authenticated",
  });
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
    {
      name: "idx",
      display_name: "Index",
      example_questions: ["q1"],
      initialized: true,
      acronyms: {},
    },
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

test("uninitialized index option disabled", async () => {
  (fetchIndexOptions as jest.Mock).mockResolvedValue([
    {
      name: "idx",
      display_name: "Index",
      example_questions: [],
      initialized: false,
      acronyms: {},
    },
  ]);
  const mockSession = { accessToken: "token" } as any;
  render(
    <SessionProvider session={mockSession}>
      <ChatWindow />
    </SessionProvider>,
  );
  const opt = await screen.findByRole("option", { name: "Index" });
  expect(opt).toBeDisabled();
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
    {
      name: "idx",
      display_name: "Index",
      example_questions: ["q"],
      initialized: true,
      acronyms: {},
    },
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
    {
      name: "idx",
      display_name: "Index",
      example_questions: ["q"],
      initialized: true,
      acronyms: {},
    },
    {
      name: "idx2",
      display_name: "Other",
      example_questions: ["q"],
      initialized: true,
      acronyms: {},
    },
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

test("index change clears messages", async () => {
  (fetchIndexOptions as jest.Mock).mockResolvedValue([
    {
      name: "a",
      display_name: "A",
      example_questions: [],
      initialized: true,
      acronyms: {},
    },
    {
      name: "b",
      display_name: "B",
      example_questions: [],
      initialized: true,
      acronyms: {},
    },
  ]);
  (fetchEventSource as jest.Mock).mockImplementation(async (_url, opts) => {
    opts.onmessage?.({
      event: "data",
      data: JSON.stringify({
        ops: [{ op: "add", path: "/streamed_output", value: ["answer"] }],
      }),
    });
    opts.onmessage?.({ event: "end" });
  });

  render(
    <SessionProvider session={null}>
      <ChatWindow />
    </SessionProvider>,
  );
  const select = await screen.findByRole("combobox");
  fireEvent.change(select, { target: { value: "a" } });
  await act(async () => {});
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "hi" } });
  fireEvent.click(screen.getByLabelText("Send"));

  await screen.findByText("hi");
  await screen.findByText("answer");

  await act(async () => {
    fireEvent.change(select, { target: { value: "b" } });
  });

  await waitFor(() => expect(screen.getByRole("textbox")).toHaveValue(""));
});

test("expands acronyms and restores on backspace", async () => {
  (fetchIndexOptions as jest.Mock).mockResolvedValue([
    {
      name: "idx",
      display_name: "Index",
      example_questions: [],
      initialized: true,
      acronyms: { HR: "Human Resources" },
    },
  ]);
  const mockSession = { accessToken: "token" } as any;
  render(
    <SessionProvider session={mockSession}>
      <ChatWindow />
    </SessionProvider>,
  );
  await screen.findByText("Select Document Index");
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "idx" } });
  const box = screen.getByRole("textbox");
  fireEvent.change(box, { target: { value: "See HR " } });
  await new Promise((r) => setTimeout(r, 20));
  expect(box).toHaveValue("See Human Resources ");
  const start = box.value.indexOf("Human Resources");
  expect(box.selectionStart).toBe(start);
  expect(box.selectionEnd).toBe(start + "Human Resources".length);
  fireEvent.keyDown(box, { key: "Backspace" });
  expect(box).toHaveValue("See HR ");
});

test("new chat button clears messages but keeps index", async () => {
  (fetchIndexOptions as jest.Mock).mockResolvedValue([
    {
      name: "idx",
      display_name: "Index",
      example_questions: ["q1"],
      initialized: true,
      acronyms: {},
    },
  ]);
  (fetchEventSource as jest.Mock).mockImplementation(async (_url, opts) => {
    opts.onmessage?.({
      event: "data",
      data: JSON.stringify({ streamed_output: ["hi"], id: "1", ops: [] }),
    });
    opts.onmessage?.({ event: "end" });
  });
  render(
    <SessionProvider session={null}>
      <ChatWindow />
    </SessionProvider>,
  );
  const select = await screen.findByRole("combobox");
  fireEvent.change(select, { target: { value: "idx" } });
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "hi" } });
  fireEvent.click(screen.getByLabelText("Send"));
  await screen.findByText("hi");

  fireEvent.click(screen.getByLabelText("start new chat"));
  await screen.findByText("q1");
  expect(select).toHaveValue("idx");
  expect(screen.queryByText("hi")).toBeNull();
});

test("shows loading state when session loading", () => {
  (useSession as jest.Mock).mockReturnValueOnce({
    data: null,
    status: "loading",
  });
  (fetchIndexOptions as jest.Mock).mockResolvedValue([]);
  render(
    <SessionProvider session={null}>
      <ChatWindow />
    </SessionProvider>,
  );
  expect(screen.getByText("Loading...")).toBeInTheDocument();
});

test("renders highlighted markdown and updates message", async () => {
  (fetchIndexOptions as jest.Mock).mockResolvedValue([
    {
      name: "idx",
      display_name: "Index",
      example_questions: [],
      initialized: true,
      acronyms: {},
    },
  ]);

  const highlightSpy = jest.spyOn(hljs, "highlight");

  (fetchEventSource as jest.Mock).mockImplementation(async (_url, opts) => {
    opts.onmessage?.({
      event: "data",
      data: JSON.stringify({
        ops: [
          {
            op: "add",
            path: "/streamed_output",
            value: ["response [0]"],
          },
          {
            op: "add",
            path: "/logs",
            value: {
              FindDocs: {
                final_output: {
                  output: [{ metadata: { file_path: "p", filename: "f" } }],
                },
              },
            },
          },
        ],
      }),
    });
    opts.onmessage?.({ event: "end" });
  });

  render(
    <SessionProvider session={null}>
      <ChatWindow />
    </SessionProvider>,
  );
  const select = await screen.findByRole("combobox");
  fireEvent.change(select, { target: { value: "idx" } });
  fireEvent.change(screen.getByRole("textbox"), {
    target: { value: "```js\nconst a = 1;\n```" },
  });
  fireEvent.click(screen.getByLabelText("Send"));

  await screen.findByText("response");

  expect(highlightSpy).toHaveBeenCalled();
  expect(screen.getByText("View Sources")).toBeInTheDocument();
  expect(screen.getByText("f")).toBeInTheDocument();
});

test("enter vs shift+enter", async () => {
  (fetchIndexOptions as jest.Mock).mockResolvedValue([
    {
      name: "idx",
      display_name: "Index",
      example_questions: [],
      initialized: true,
      acronyms: {},
    },
  ]);
  (fetchEventSource as jest.Mock).mockImplementation(async (_url, opts) => {
    opts.onmessage?.({ event: "end" });
  });
  render(
    <SessionProvider session={null}>
      <ChatWindow />
    </SessionProvider>,
  );
  const select = await screen.findByRole("combobox");
  fireEvent.change(select, { target: { value: "idx" } });
  const box = screen.getByRole("textbox");
  fireEvent.change(box, { target: { value: "line" } });
  fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
  expect(box).toHaveValue("line\n");

  fireEvent.keyDown(box, { key: "Enter" });
  await waitFor(() => expect(fetchEventSource).toHaveBeenCalled());
});
