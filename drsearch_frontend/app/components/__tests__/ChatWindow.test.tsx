import { render, screen, waitFor } from "@testing-library/react";
import { SessionProvider } from "next-auth/react";
import { ChatWindow } from "../ChatWindow";
import { fetchIndexOptions } from "../../utils/fetchIndexOptions";

jest.mock("../../utils/fetchIndexOptions", () => ({
  fetchIndexOptions: jest.fn(),
}));

test("renders EmptyState when no messages", async () => {
  (fetchIndexOptions as jest.Mock).mockResolvedValue([]);

  const mockSession = {
    accessToken: "test-token",
  } as any;

  render(
    <SessionProvider session={mockSession}>
      <ChatWindow />
    </SessionProvider>,
  );

  await waitFor(() =>
    expect(screen.getByText("DRS ASSISTANT")).toBeInTheDocument(),
  );
});
