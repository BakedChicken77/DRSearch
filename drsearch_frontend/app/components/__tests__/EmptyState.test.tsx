import { render, screen, fireEvent } from "@testing-library/react";
import { EmptyState } from "../EmptyState";

const options = [
  {
    name: "index1",
    display_name: "Index 1",
    example_questions: ["q1", "q2", "q3", "q4"],
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
