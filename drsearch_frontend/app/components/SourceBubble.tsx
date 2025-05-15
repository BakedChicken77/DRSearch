// app\components\SourceBubble.tsx

import "react-toastify/dist/ReactToastify.css";
import { Card, CardBody, Heading } from "@chakra-ui/react";
import { sendFeedback } from "../utils/sendFeedback";
import { convertToHttpUrlIfNeeded } from "../utils/urlUtils";

export type Source = {
  url: string | undefined; // Make url optional
  title: string;
};

export function SourceBubble({
  source,
  highlighted,
  onMouseEnter,
  onMouseLeave,
  runId,
}: {
  source: Source;
  highlighted: boolean;
  onMouseEnter: () => any;
  onMouseLeave: () => any;
  runId?: string;
}) {
  console.log("Source object:", source);

  const fileUrl = source.url ? convertToHttpUrlIfNeeded(source.url) : "";
  const filetitle = source.title || "";

  console.log("Source URL:", fileUrl);
  console.log("Source title:", filetitle);

  return (
    <Card
      onClick={async () => {
        if (fileUrl) {
          const a = document.createElement('a');
          a.href = fileUrl;
          a.target = "_blank";
          a.rel = "noopener noreferrer"; // Security best practice
          a.style.display = 'none';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          console.log("Opened file URL:", fileUrl);
        } else {
          console.warn("File URL is undefined, cannot open file");
        }
        if (runId) {
          await sendFeedback({
            key: "user_click",
            runId,
            value: fileUrl,
            isExplicit: false,
          });
          console.log("Feedback sent for runId:", runId);
        }
      }}
      backgroundColor={highlighted ? "rgb(25,32,42)" : "rgb(45,52,62)"}
      onMouseEnter={() => {
        onMouseEnter();
        console.log("Mouse entered on source bubble");
      }}
      onMouseLeave={() => {
        onMouseLeave();
        console.log("Mouse left source bubble");
      }}
      cursor={"pointer"}
      alignSelf={"stretch"}
      height="100%"
      overflow={"hidden"}
    >
      <CardBody>
        <Heading size={"sm"} fontWeight={"normal"} color={"white"}>
          {filetitle || "Unknown Document"}
        </Heading>
      </CardBody>
    </Card>
  );
}
