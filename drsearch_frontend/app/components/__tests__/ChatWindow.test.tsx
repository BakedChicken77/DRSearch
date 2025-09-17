import React from "react";
import {
  render,
  screen,
  waitFor,
  within,
  fireEvent,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SessionProvider, useSession } from "next-auth/react";
import { ChatWindow } from "../ChatWindow";
import { fetchIndexOptions } from "../../utils/fetchIndexOptions";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import hljs from "highlight.js";

jest.mock("next/dynamic", () => {
  const React = require("react");
  return (importer: () => Promise<any>) => {
    return function DynamicComponent(props: unknown) {
      const [Loaded, setLoaded] = React.useState<any>(null);
      React.useEffect(() => {
        let mounted = true;
        importer().then((mod) => {
          if (mounted) {
            setLoaded(() => mod.default ?? mod);
          }
        });
        return () => {
          mounted = false;
        };
      }, []);
      if (!Loaded) return null;
      return React.createElement(Loaded, props);
    };
  };
});

jest.mock("../../utils/fetchIndexOptions", () => ({
  fetchIndexOptions: jest.fn(),
}));

jest.mock("@microsoft/fetch-event-source", () => ({
  fetchEventSource: jest.fn(),
}));

jest.mock("next-auth/react", () => ({
  __esModule: true,
  SessionProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useSession: jest.fn(),
}));

const mockFetchEventSource = fetchEventSource as jest.MockedFunction<
  typeof fetchEventSource
>;
const mockFetchIndexOptions = fetchIndexOptions as jest.MockedFunction<
  typeof fetchIndexOptions
>;
const mockUseSession = useSession as jest.Mock;

type StreamEvent =
  | { type: "data"; data: Record<string, unknown> }
  | { type: "end" };

const BASIC_INDEX = {
  name: "idx",
  display_name: "Index",
  example_questions: ["Example question"],
  initialized: true,
  acronyms: { HR: "Human Resources" },
};

async function renderChatWindow({
  options = [BASIC_INDEX],
  authEnabled = false,
  session = null,
  sessionStatus,
  waitForEditor = true,
  waitForIndexSelect = true,
}: {
  options?: typeof BASIC_INDEX[];
  authEnabled?: boolean;
  session?: any;
  sessionStatus?: "authenticated" | "loading" | "unauthenticated";
  waitForEditor?: boolean;
  waitForIndexSelect?: boolean;
} = {}) {
  mockFetchIndexOptions.mockResolvedValue(options);
  process.env.NEXT_PUBLIC_AUTH_ENABLED = authEnabled ? "True" : "False";
  mockUseSession.mockReturnValue({
    data: session,
    status:
      sessionStatus ?? (session ? "authenticated" : authEnabled ? "unauthenticated" : "unauthenticated"),
  });

  const user = userEvent.setup();

  render(
    <SessionProvider session={session}>
      <ChatWindow />
    </SessionProvider>,
  );

  if (waitForEditor) {
    await screen.findByRole("textbox");
  }

  await waitFor(() => expect(mockFetchIndexOptions).toHaveBeenCalled());
  if (waitForIndexSelect) {
    await screen.findByTestId("index-select");
  }

  return { user };
}

function mockStream(events: StreamEvent[]) {
  mockFetchEventSource.mockImplementation(async (_url, options) => {
    options?.onopen?.({} as any);
    for (const event of events) {
      await Promise.resolve();
      if (event.type === "data") {
        options?.onmessage?.({
          event: "data",
          data: JSON.stringify(event.data),
        });
      } else {
        options?.onmessage?.({ event: "end" });
      }
    }
    return undefined;
  });
}

function getIndexSelect() {
  return screen.getByTestId("index-select") as HTMLSelectElement;
}

function getEditor() {
  return screen.getByRole("textbox");
}

beforeEach(() => {
  jest.clearAllMocks();
  process.env.NEXT_PUBLIC_AUTH_ENABLED = "False";
});

let consoleLogSpy: jest.SpyInstance;

beforeAll(() => {
  if (typeof document !== "undefined") {
    (document as any).elementFromPoint = (_x: number, _y: number) =>
      document.querySelector('[contenteditable="true"]') ??
      document.body ??
      document.createElement("div");
  }
  const rect = {
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    width: 0,
    height: 0,
    x: 0,
    y: 0,
    toJSON() {
      return this;
    },
  } as DOMRect;
  const rectList = [rect] as unknown as DOMRectList;

  const getClientRects = () => rectList;
  const getBoundingClientRect = () => rect;

  Object.defineProperty(Element.prototype, "getClientRects", {
    value: getClientRects,
  });
  Object.defineProperty(Element.prototype, "getBoundingClientRect", {
    value: getBoundingClientRect,
  });

  if (typeof Node !== "undefined") {
    Object.defineProperty(Node.prototype, "getClientRects", {
      value: getClientRects,
    });
    Object.defineProperty(Node.prototype, "getBoundingClientRect", {
      value: getBoundingClientRect,
    });
  }

  const patchView = (mod: any) => {
    if (mod?.EditorView) {
      mod.EditorView.prototype.scrollToSelection = () => {};
    }
  };
  try {
    patchView(require("@tiptap/pm/view"));
  } catch (err) {
    // ignore if module resolution fails in tests
  }
  try {
    patchView(require("prosemirror-view"));
  } catch (err) {
    // ignore if module resolution fails in tests
  }

  consoleLogSpy = jest.spyOn(console, "log").mockImplementation(() => {});
});

afterAll(() => {
  consoleLogSpy.mockRestore();
});

describe("ChatWindow", () => {
  test("renders the empty state heading when no messages", async () => {
    await renderChatWindow({ options: [BASIC_INDEX] });

    expect(await screen.findByText("DRS ASSISTANT")).toBeInTheDocument();
    expect(screen.getByText("Select Document Index")).toBeInTheDocument();
  });

  test("does not send when no index is selected", async () => {
    const { user } = await renderChatWindow();

    const editor = getEditor();
    await user.click(editor);
    await user.type(editor, "Hello there");
    await user.keyboard("{Enter}");

    expect(mockFetchEventSource).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Send")).toBeDisabled();
  });

  test("streams a response when choosing an example question", async () => {
    const highlightSpy = jest
      .spyOn(hljs, "highlight")
      .mockReturnValue({ value: "highlighted" } as any);
    const { user } = await renderChatWindow();

    await user.selectOptions(getIndexSelect(), "idx");
    await waitFor(() =>
      expect(screen.getByLabelText("Send")).not.toBeDisabled(),
    );
    await screen.findByText("Example question");

    mockStream([
      {
        type: "data",
        data: {
          ops: [
            { op: "add", path: "/streamed_output", value: ["Partial "] },
          ],
        },
      },
      {
        type: "data",
        data: {
          ops: [
            {
              op: "replace",
              path: "/streamed_output",
              value: ["Partial ", "```js\nconst a = 1;\n```"],
            },
            {
              op: "add",
              path: "/logs",
              value: {
                FindDocs: {
                  final_output: {
                    output: [
                      { metadata: { file_path: "path/to/doc", filename: "Doc" } },
                    ],
                  },
                },
              },
            },
            { op: "add", path: "/id", value: "run-1" },
          ],
        },
      },
      { type: "end" },
    ]);

    const exampleCard = screen.getByText("Example question");
    await user.click(exampleCard);
    fireEvent.mouseUp(exampleCard);

    await waitFor(() => expect(mockFetchEventSource).toHaveBeenCalled());

    const body = mockFetchEventSource.mock.calls[0][1]?.body as string;
    const parsed = JSON.parse(body);
    expect(parsed.input.index_name).toBe("idx");
    expect(parsed.input.question).toBe("Example question");

    await screen.findByText(/Partial/);

    highlightSpy.mockRestore();
  });

  test("settings changes propagate into the payload", async () => {
    const { user } = await renderChatWindow();

    await user.selectOptions(getIndexSelect(), "idx");
    await waitFor(() =>
      expect(screen.getByLabelText("Send")).not.toBeDisabled(),
    );
    mockStream([{ type: "end" }]);

    await user.click(screen.getByLabelText("Open settings"));

    const docsInput = await screen.findByRole("spinbutton", {
      name: /documents to retrieve/i,
    });
    await user.click(docsInput);
    await user.keyboard("{ArrowUp}");
    expect(docsInput).toHaveValue("4");
    await user.click(screen.getByLabelText("Close"));

    const editor = getEditor();
    fireEvent.input(editor, { target: { textContent: "Payload test" } });
    await user.click(screen.getByLabelText("Send"));

    await waitFor(() => expect(mockFetchEventSource).toHaveBeenCalled());

    const body = mockFetchEventSource.mock.calls[0][1]?.body as string;
    const parsed = JSON.parse(body);
    expect(parsed.input.num_docs_retrieved).toBe(4);
    expect(parsed.input.question).toBe("Payload test");
  });

  test("changing the index clears chat history and input", async () => {
    const { user } = await renderChatWindow({
      options: [
        BASIC_INDEX,
        {
          name: "idx-2",
          display_name: "Second",
          example_questions: [],
          initialized: true,
          acronyms: {},
        },
      ],
    });

    mockStream([{ type: "end" }]);

    await user.selectOptions(getIndexSelect(), "idx");
    await waitFor(() =>
      expect(screen.getByLabelText("Send")).not.toBeDisabled(),
    );

    const editor = getEditor();
    fireEvent.input(editor, { target: { textContent: "Hello world" } });
    await user.click(screen.getByLabelText("Send"));
    await waitFor(() => expect(mockFetchEventSource).toHaveBeenCalledTimes(1));
    const firstBody = JSON.parse(
      mockFetchEventSource.mock.calls[0][1]?.body as string,
    );
    expect(firstBody.input.question).toBe("Hello world");

    await user.selectOptions(getIndexSelect(), "idx-2");

    await waitFor(() =>
      expect(screen.getByTestId("chat-stream").textContent?.trim()).toBe(""),
    );
    await waitFor(() => expect(getEditor()).toHaveTextContent(""));
  });

  test("acronym expansion occurs and backspace restores the acronym", async () => {
    mockStream([{ type: "end" }]);
    const { user } = await renderChatWindow();

    await user.selectOptions(getIndexSelect(), "idx");
    await waitFor(() =>
      expect(screen.getByLabelText("Send")).not.toBeDisabled(),
    );

    const editor = getEditor();
    fireEvent.input(editor, {
      target: { textContent: "See Human Resources " },
    });
    await user.click(screen.getByLabelText("Send"));

    await waitFor(() => expect(mockFetchEventSource).toHaveBeenCalledTimes(1));
    const firstBody = JSON.parse(
      mockFetchEventSource.mock.calls[0][1]?.body as string,
    );
    expect(firstBody.input.question).toContain("Human Resources");

    const editorAfterSend = getEditor();
    fireEvent.input(editorAfterSend, {
      target: { textContent: "See HR" },
    });
    await user.click(screen.getByLabelText("Send"));

    await waitFor(() => expect(mockFetchEventSource).toHaveBeenCalledTimes(2));
    const secondBody = JSON.parse(
      mockFetchEventSource.mock.calls[1][1]?.body as string,
    );
    expect(secondBody.input.question.trim()).toBe("See HR");
  });

  test("shift+enter inserts a newline and enter triggers send", async () => {
    const { user } = await renderChatWindow();

    mockStream([{ type: "end" }]);
    await user.selectOptions(getIndexSelect(), "idx");

    const editor = getEditor();
    await user.click(editor);
    await user.type(editor, "line");
    await user.keyboard("{Shift>}{Enter}{/Shift}");

    await waitFor(() =>
      expect(
        (editor as HTMLElement).querySelectorAll("br").length,
      ).toBeGreaterThan(1),
    );

    await user.keyboard("{Enter}");

    await waitFor(() => expect(mockFetchEventSource).toHaveBeenCalled());
    await waitFor(() => expect(editor).toHaveTextContent(""));
  });

  test("shows a loading state when auth is enabled and session is loading", async () => {
    await renderChatWindow({
      authEnabled: true,
      session: null,
      sessionStatus: "loading",
      waitForEditor: false,
      waitForIndexSelect: false,
    });

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  test("marks uninitialized index options as disabled", async () => {
    await renderChatWindow({
      options: [
        {
          name: "pending",
          display_name: "Pending",
          example_questions: [],
          initialized: false,
          acronyms: {},
        },
      ],
    });

    const select = getIndexSelect();
    const option = within(select).getByRole("option", { name: "Pending" });
    expect(option).toBeDisabled();
  });
});
