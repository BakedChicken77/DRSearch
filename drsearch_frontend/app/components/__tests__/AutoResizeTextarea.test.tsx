import { render, screen } from "@testing-library/react";
import { AutoResizeTextarea } from "../AutoResizeTextarea";

test("renders textarea with placeholder", () => {
  render(<AutoResizeTextarea placeholder="test" />);
  expect(screen.getByPlaceholderText("test")).toBeInTheDocument();
});
