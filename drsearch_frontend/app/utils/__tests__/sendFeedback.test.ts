import { sendFeedback } from "../sendFeedback";
import { apiBaseUrl } from "../constants";
import { v4 as uuidv4 } from "uuid";

jest.mock("uuid");

beforeEach(() => {
  (global.fetch as any) = jest.fn();
  (uuidv4 as jest.Mock).mockReturnValue("uuid");
});

afterEach(() => {
  jest.resetAllMocks();
});

test("posts feedback when no id provided", async () => {
  (fetch as jest.Mock).mockResolvedValue({
    json: () => Promise.resolve({ code: 200, result: "ok" }),
  });
  const res = await sendFeedback({
    key: "k",
    runId: "r",
    score: 1,
    value: "v",
    comment: "c",
    isExplicit: true,
  });
  expect(fetch).toHaveBeenCalledWith(
    apiBaseUrl + "/feedback",
    expect.objectContaining({ method: "POST" }),
  );
  const body = JSON.parse((fetch as jest.Mock).mock.calls[0][1].body);
  expect(body.key).toBe("k");
  expect(res).toEqual({ code: 200, result: "ok", feedbackId: "uuid" });
});

test("patches feedback when id provided", async () => {
  (fetch as jest.Mock).mockResolvedValue({
    json: () => Promise.resolve({ code: 200, result: "ok" }),
  });
  const res = await sendFeedback({
    key: "k",
    runId: "r",
    feedbackId: "f",
    isExplicit: false,
  });
  expect(fetch).toHaveBeenCalledWith(
    apiBaseUrl + "/feedback",
    expect.objectContaining({ method: "PATCH" }),
  );
  expect(res.feedbackId).toBe("f");
});

test("includes comment in request body when provided", async () => {
  (fetch as jest.Mock).mockResolvedValue({
    json: () => Promise.resolve({ code: 200, result: "ok" }),
  });
  await sendFeedback({
    key: "k",
    runId: "r",
    comment: "my comment",
    isExplicit: true,
  });
  const body = JSON.parse((fetch as jest.Mock).mock.calls[0][1].body);
  expect(body.comment).toBe("my comment");
});

test("omits comment from request body when not provided", async () => {
  (fetch as jest.Mock).mockResolvedValue({
    json: () => Promise.resolve({ code: 200, result: "ok" }),
  });
  await sendFeedback({
    key: "k",
    runId: "r",
    feedbackId: "f",
    isExplicit: true,
  });
  const body = JSON.parse((fetch as jest.Mock).mock.calls[0][1].body);
  expect(body).not.toHaveProperty("comment");
});

test("adds authorization header when token provided", async () => {
  (fetch as jest.Mock).mockResolvedValue({
    json: () => Promise.resolve({ code: 200, result: "ok" }),
  });
  await sendFeedback({
    key: "k",
    runId: "r",
    accessToken: "abc",
    isExplicit: true,
  });
  const headers = (fetch as jest.Mock).mock.calls[0][1].headers;
  expect(headers.Authorization).toBe("Bearer abc");
});
