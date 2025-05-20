import { render, screen } from "@testing-library/react";
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
