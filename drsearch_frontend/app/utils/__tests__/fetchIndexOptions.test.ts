import { fetchIndexOptions } from "../fetchIndexOptions";

const apiUrl = "http://localhost:8011/index-options";

beforeEach(() => {
  (global.fetch as any) = jest.fn();
});

afterEach(() => {
  jest.resetAllMocks();
});

test("fetches index options with token", async () => {
  (fetch as jest.Mock).mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ code: 200, result: [{ name: "a" }] }),
  });
  const res = await fetchIndexOptions("tok");
  expect(fetch).toHaveBeenCalledWith(apiUrl, {
    headers: { Authorization: "Bearer tok" },
  });
  expect(res).toEqual([{ name: "a" }]);
});

test("throws error on http failure", async () => {
  (fetch as jest.Mock).mockResolvedValue({
    ok: false,
    status: 500,
    text: () => Promise.resolve("fail"),
    statusText: "error",
  });
  await expect(fetchIndexOptions()).rejects.toThrow(
    "Failed to fetch index options: 500 – fail",
  );
});

test("throws error on malformed data", async () => {
  (fetch as jest.Mock).mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ code: 400, result: null }),
  });
  await expect(fetchIndexOptions()).rejects.toThrow(
    "Backend returned malformed data",
  );
});
