import { convertToHttpUrlIfNeeded } from "../urlUtils";

test("converts UNC path to http url", () => {
  const unc = "\\\\home.drs.com@ssl\\DavWWWRoot\\folder\\My File.txt";
  const expected = "https://home.drs.com/folder/My%20File.txt?web=1";
  expect(convertToHttpUrlIfNeeded(unc)).toBe(expected);
});

test("returns original string when pattern not matched", () => {
  const path = "/some/other/path.txt";
  expect(convertToHttpUrlIfNeeded(path)).toBe(path);
});
