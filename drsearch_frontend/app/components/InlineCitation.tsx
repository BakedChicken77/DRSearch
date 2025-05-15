// app\components\InlineCitation.tsx

import { Source } from "./SourceBubble";
import { convertToHttpUrlIfNeeded } from "../utils/urlUtils";

export function InlineCitation(props: {
  source: Source;
  sourceNumber: number;
  highlighted: boolean;
  onMouseEnter: () => any;
  onMouseLeave: () => any;
}) {
  const { source, sourceNumber, highlighted, onMouseEnter, onMouseLeave } = props;

  console.log("InlineCitation props:", props);
  
  const fileUrl = source?.url ? convertToHttpUrlIfNeeded(source.url) : "";
  
  return (
    <a
      href={fileUrl}
      target="_blank"
      className={`relative bottom-1.5 text-xs border rounded px-1 ${
        highlighted ? "bg-[rgb(200, 1, 24)]" : "bg-[rgb(228, 1, 44)]"
      }`}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {sourceNumber}
    </a>
  );
}