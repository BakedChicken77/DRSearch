import { render } from "@testing-library/react";
import { filterSources, createAnswerElements } from "../ChatMessageBubble";
import React from "react";

test("filters duplicate sources", () => {
  const sources = [
    { url: "a", title: "A" },
    { url: "a", title: "A2" },
    { url: "b", title: "B" },
  ];
  const { filtered, indexMap } = filterSources(sources as any);
  expect(filtered.length).toBe(2);
  expect(indexMap.get(1)).toBe(0);
});

test("creates citation elements", () => {
  const sources = [{ url: "a", title: "A" }];
  const { filtered, indexMap } = filterSources(sources as any);
  const res = createAnswerElements(
    "test [1]",
    filtered as any,
    indexMap,
    [false],
    jest.fn(),
  );
  const { container } = render(<>{res}</>);
  expect(container.querySelector("a")).toBeTruthy();
});
