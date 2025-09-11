import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AcronymTextarea } from "../AcronymTextarea";

function Wrapper() {
  const [val, setVal] = React.useState("");
  return (
    <AcronymTextarea
      value={val}
      onChange={setVal}
      acronymMap={{ TLA: "three letter acronym" }}
      placeholder="test"
    />
  );
}

test("acronym expansion is styled and persists until removed", async () => {
  const user = userEvent.setup();
  render(<Wrapper />);
  const textarea = screen.getByPlaceholderText("test");
  await user.type(textarea, "This is a TLA ");
  const overlay = screen.getByTestId("acronym-overlay");
  expect(overlay.innerHTML).toContain(
    '<span class="acronym-replacement">three letter acronym</span>',
  );
  await user.type(textarea, "test");
  expect(overlay.innerHTML).toContain(
    '<span class="acronym-replacement">three letter acronym</span>',
  );
  await user.type(textarea, "{backspace}{backspace}{backspace}{backspace}");
  expect(overlay.innerHTML).toContain(
    '<span class="acronym-replacement">three letter acronym</span>',
  );
  await user.type(textarea, "{backspace}");
  expect(overlay.innerHTML).not.toContain("acronym-replacement");
  expect((textarea as HTMLTextAreaElement).value).toContain("TLA ");
});
