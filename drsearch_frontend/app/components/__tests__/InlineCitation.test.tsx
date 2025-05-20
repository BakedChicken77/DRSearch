import { render, screen, fireEvent } from "@testing-library/react";
import { InlineCitation } from "../InlineCitation";

test("renders citation link", () => {
  const source = { url: "http://example.com", title: "Example" };
  render(
    <InlineCitation
      source={source}
      sourceNumber={1}
      highlighted={false}
      onMouseEnter={() => {}}
      onMouseLeave={() => {}}
    />,
  );
  const link = screen.getByText("1") as HTMLAnchorElement;
  expect(link.href).toContain("http://example.com");
});

test("sanitizes UNC url and highlights when true", () => {
  const unc = "\\\\home.drs.com@ssl\\DavWWWRoot\\folder\\My File.txt";
  const expected = "https://home.drs.com/folder/My%20File.txt?web=1";
  const enter = jest.fn();
  const leave = jest.fn();
  render(
    <InlineCitation
      source={{ url: unc, title: "Doc" }}
      sourceNumber={2}
      highlighted={true}
      onMouseEnter={enter}
      onMouseLeave={leave}
    />,
  );
  const link = screen.getByText("2");
  expect(link).toHaveAttribute("href", expected);
  expect(link.className).toContain("bg-[rgb(200, 1, 24)]");
  fireEvent.mouseEnter(link);
  fireEvent.mouseLeave(link);
  expect(enter).toHaveBeenCalled();
  expect(leave).toHaveBeenCalled();
});

test("renders multiple citations with varying props", () => {
  render(
    <>
      <InlineCitation
        source={{ url: "http://a.com", title: "A" }}
        sourceNumber={3}
        highlighted={false}
        onMouseEnter={() => {}}
        onMouseLeave={() => {}}
      />
      <InlineCitation
        source={{ url: undefined, title: "B" }}
        sourceNumber={4}
        highlighted={false}
        onMouseEnter={() => {}}
        onMouseLeave={() => {}}
      />
    </>,
  );
  const linkA = screen.getByText("3") as HTMLAnchorElement;
  const linkB = screen.getByText("4") as HTMLAnchorElement;
  expect(linkA).toHaveAttribute("href", "http://a.com");
  expect(linkB).toHaveAttribute("href", "");
});
