import { render, screen } from "@testing-library/react";
import { ChatWindow } from "../ChatWindow";

test("renders EmptyState when no messages", () => {
  render(<ChatWindow />);
  expect(screen.getByText("DRS ASSISTANT")).toBeInTheDocument();
});
