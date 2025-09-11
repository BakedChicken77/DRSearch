import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AutoResizeTextarea } from "../AutoResizeTextarea";

function Wrapper() {
  const [val, setVal] = React.useState("");
  return (
    <AutoResizeTextarea
      value={val}
      onChange={setVal}
      acronymMap={{ TLA: "three letter acronym" }}
      placeholder="test"
    />
  );
}

test("acronym expansion is applied and can be removed", async () => {
  const user = userEvent.setup();
  render(<Wrapper />);
  const textarea = screen.getByPlaceholderText("test");
  await user.type(textarea, "This is a TLA ");
  expect((textarea as HTMLTextAreaElement).value).toBe(
    "This is a three letter acronym ",
  );
  await new Promise((r) => setTimeout(r, 50));
  await user.type(textarea, "test");
  expect((textarea as HTMLTextAreaElement).value).toBe(
    "This is a three letter acronym test",
  );
  await user.type(textarea, "{backspace}{backspace}{backspace}{backspace}");
  expect((textarea as HTMLTextAreaElement).value).toBe(
    "This is a three letter acronym ",
  );
  await user.type(textarea, "{backspace}");
  expect((textarea as HTMLTextAreaElement).value).toBe("This is a TLA ");
});
