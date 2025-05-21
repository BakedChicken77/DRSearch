import { fetchIndexOptions } from "../fetchIndexOptions";
import { sendFeedback } from "../sendFeedback";
import { apiBaseUrl } from "../constants";

beforeEach(() => {
  (global.fetch as any) = jest.fn();
});

afterEach(() => {
  jest.resetAllMocks();
});

test("fetchIndexOptions and sendFeedback roundtrip", async () => {
  // Backend index option response
  (fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    json: () => Promise.resolve({ code: 200, result: [{ name: "a" }] }),
  });
  const opts = await fetchIndexOptions();
  expect(opts).toEqual([{ name: "a" }]);

  // Feedback response
  (fetch as jest.Mock).mockResolvedValueOnce({
    json: () => Promise.resolve({ code: 200, result: "ok" }),
  });
  const feedback = await sendFeedback({
    key: "user_score",
    runId: "r",
    isExplicit: true,
  });
  expect(fetch).toHaveBeenCalledWith(
    apiBaseUrl + "/feedback",
    expect.anything(),
  );
  expect(feedback.code).toBe(200);
});
