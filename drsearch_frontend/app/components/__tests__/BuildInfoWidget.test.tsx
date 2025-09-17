import { render, screen, within } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";

import {
  BuildInfoWidget,
  __resetBackendBuildInfoCacheForTests as resetBackendBuildInfoCache,
} from "../BuildInfoWidget";

jest.mock("@chakra-ui/react", () => {
  const actual = jest.requireActual("@chakra-ui/react");
  return {
    ...actual,
    Tooltip: ({
      label,
      children,
      hasArrow: _hasArrow,
      openDelay: _openDelay,
      closeDelay: _closeDelay,
      ...rest
    }: any) => (
      <div {...rest}>
        {children}
        <div data-testid="tooltip-label">{label}</div>
      </div>
    ),
  };
});

describe("BuildInfoWidget", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
    resetBackendBuildInfoCache();
  });

  afterEach(() => {
    process.env = originalEnv;
    jest.clearAllMocks();
    // @ts-expect-error - clean up fetch mock between tests
    delete global.fetch;
    resetBackendBuildInfoCache();
  });

  function renderWidget() {
    return render(
      <ChakraProvider>
        <BuildInfoWidget />
      </ChakraProvider>,
    );
  }

  test("shows frontend and backend build details on hover", async () => {
    process.env.NEXT_PUBLIC_BUILD_SHA = "frontend-long-sha";
    process.env.NEXT_PUBLIC_BUILD_SHA_SHORT = "frontsha";
    process.env.NEXT_PUBLIC_BUILD_DATE = "2024-05-15";

    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        code: 200,
        result: [],
        build_info: {
          sha: "backend-long-sha",
          sha_short: "backsha",
          build_date: "2024-05-14",
        },
      }),
    });
    // @ts-expect-error - provide fetch mock for the test environment
    global.fetch = fetchMock;

    renderWidget();

    const tooltip = await screen.findByTestId("tooltip-label");
    expect(within(tooltip).getByText(/^Frontend$/i)).toBeInTheDocument();
    expect(
      within(tooltip).getByText("frontsha", { selector: "code" }),
    ).toBeInTheDocument();
    expect(
      within(tooltip).getByText("frontend-long-sha", { selector: "code" }),
    ).toBeInTheDocument();
    expect(within(tooltip).getByText(/Built: 2024-05-15/i)).toBeInTheDocument();

    expect(within(tooltip).getByText(/^Backend$/i)).toBeInTheDocument();
    expect(
      await within(tooltip).findByText("backsha", { selector: "code" }),
    ).toBeInTheDocument();
    expect(
      await within(tooltip).findByText("backend-long-sha", { selector: "code" }),
    ).toBeInTheDocument();
    expect(within(tooltip).getByText(/Built: 2024-05-14/i)).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  test("falls back to unknown when backend build info missing", async () => {
    process.env.NEXT_PUBLIC_BUILD_SHA = "frontend-long-sha";
    process.env.NEXT_PUBLIC_BUILD_SHA_SHORT = "frontsha";
    process.env.NEXT_PUBLIC_BUILD_DATE = "2024-05-15";

    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ code: 200, result: [] }),
    });
    // @ts-expect-error - provide fetch mock for the test environment
    global.fetch = fetchMock;

    renderWidget();

    const tooltip = await screen.findByTestId("tooltip-label");
    expect(within(tooltip).getByText(/^Backend$/i)).toBeInTheDocument();
    expect(within(tooltip).getAllByText(/unknown/i).length).toBeGreaterThanOrEqual(3);
  });

  test("reuses the backend build info request across instances", async () => {
    process.env.NEXT_PUBLIC_BUILD_SHA = "frontend-long-sha";
    process.env.NEXT_PUBLIC_BUILD_SHA_SHORT = "frontsha";
    process.env.NEXT_PUBLIC_BUILD_DATE = "2024-05-15";

    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        code: 200,
        result: [],
        build_info: {
          sha: "backend-long-sha",
          sha_short: "backsha",
          build_date: "2024-05-14",
        },
      }),
    });
    // @ts-expect-error - provide fetch mock for the test environment
    global.fetch = fetchMock;

    render(
      <ChakraProvider>
        <BuildInfoWidget />
        <BuildInfoWidget />
      </ChakraProvider>,
    );

    await screen.findAllByText("Build");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
