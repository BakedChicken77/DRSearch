import { fetchDocumentList } from "../fetchDocumentList";

const apiUrl = "http://localhost:8011/documents?index=test";

beforeEach(() => {
  (global.fetch as any) = jest.fn();
});

afterEach(() => {
  jest.resetAllMocks();
});

test("fetches document list with token", async () => {
  (fetch as jest.Mock).mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ code: 200, result: ["a"] }),
  });
  const res = await fetchDocumentList("test", "tok");
  expect(fetch).toHaveBeenCalledWith(apiUrl, {
    headers: { Authorization: "Bearer tok" },
  });
  expect(res).toEqual(["a"]);
});

test("throws error on http failure", async () => {
  (fetch as jest.Mock).mockResolvedValue({
    ok: false,
    status: 500,
    text: () => Promise.resolve("fail"),
    statusText: "error",
  });
  await expect(fetchDocumentList("test")).rejects.toThrow(
    "Failed to fetch document list: 500 – fail",
  );
});

test("uses statusText when error body empty", async () => {
  (fetch as jest.Mock).mockResolvedValue({
    ok: false,
    status: 404,
    text: () => Promise.resolve(""),
    statusText: "Not Found",
  });
  await expect(fetchDocumentList("test")).rejects.toThrow(
    "Failed to fetch document list: 404 – Not Found",
  );
});

test("throws error on malformed data", async () => {
  (fetch as jest.Mock).mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ code: 400, result: null }),
  });
  await expect(fetchDocumentList("test")).rejects.toThrow(
    "Backend returned malformed data",
  );
});
