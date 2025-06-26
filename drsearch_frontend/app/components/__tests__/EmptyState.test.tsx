import { render, screen, fireEvent } from "@testing-library/react";
import { EmptyState } from "../EmptyState";

const options = [
  {
    name: "index1",
    display_name: "Index 1",
    example_questions: ["q1", "q2", "q3", "q4"],
    initialized: true,
  },
];

test("shows spinner when loading", () => {
  render(
    <EmptyState
      onChoice={() => {}}
      selectedIndexName=""
      setSelectedIndexName={() => {}}
      indexOptions={null}
      loadingOptions={true}
    />,
  );
  expect(screen.getByRole("status")).toBeInTheDocument();
});

test("calls onChoice when card clicked", () => {
  const onChoice = jest.fn();
  const setIndex = jest.fn();
  render(
    <EmptyState
      onChoice={onChoice}
      selectedIndexName="index1"
      setSelectedIndexName={setIndex}
      indexOptions={options}
      loadingOptions={false}
    />,
  );
  fireEvent.mouseUp(screen.getByText("q1"));
  expect(onChoice).toHaveBeenCalledWith("q1");
});

test("renders all example options and handles hover and click", () => {
  const onChoice = jest.fn();
  render(
    <EmptyState
      onChoice={onChoice}
      selectedIndexName="index1"
      setSelectedIndexName={() => {}}
      indexOptions={options}
      loadingOptions={false}
    />,
  );

  options[0].example_questions.forEach((q) => {
    const heading = screen.getByText(q);
    const card = heading.closest(".chakra-card") as HTMLElement;
    expect(card).toBeInTheDocument();
    expect(getComputedStyle(card).cursor).toBe("pointer");
    fireEvent.mouseEnter(card);
    expect(getComputedStyle(card).backgroundColor).toBe("rgb(78, 78, 81)");
    fireEvent.mouseLeave(card);
    fireEvent.mouseUp(card);
    expect(onChoice).toHaveBeenCalledWith(q);
  });
  expect(onChoice).toHaveBeenCalledTimes(options[0].example_questions.length);
});

test("uninitialized options are disabled", () => {
  render(
    <EmptyState
      onChoice={() => {}}
      selectedIndexName=""
      setSelectedIndexName={() => {}}
      indexOptions={[
        {
          name: "i",
          display_name: "I",
          example_questions: [],
          initialized: false,
        },
      ]}
      loadingOptions={false}
    />,
  );
  expect(screen.getByRole("option", { name: "I" })).toBeDisabled();
});

test("handles indexes without example_questions gracefully", () => {
  render(
    <EmptyState
      onChoice={() => {}}
      selectedIndexName="index1"
      setSelectedIndexName={() => {}}
      indexOptions={[
        {
          name: "index1",
          display_name: "Index 1",
          // example_questions is intentionally omitted
          initialized: true,
        },
      ]}
      loadingOptions={false}
    />,
  );
  
  // Should render without crashing and not show any example question cards
  expect(screen.getByText("DRS ASSISTANT")).toBeInTheDocument();
  expect(screen.getByText("Index 1")).toBeInTheDocument();
  // No example question cards should be rendered
  expect(screen.queryByText("q1")).not.toBeInTheDocument();
});
