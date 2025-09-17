import fs from "fs";

export function extractFinalOutput(tracePath: string): string {
  const data = fs.readFileSync(tracePath, "utf-8");
  let last: string | null = null;
  for (const line of data.split(/\r?\n/)) {
    if (!line.startsWith("data: ")) continue;
    try {
      const obj = JSON.parse(line.slice(6));
      if (Array.isArray(obj.ops)) {
        for (const op of obj.ops) {
          if (typeof op.path === "string" && op.path.endsWith("final_output")) {
            const val = op.value?.output;
            if (typeof val === "string") {
              last = val;
            }
          }
        }
      }
    } catch {
      // ignore malformed JSON
    }
  }
  if (last === null) {
    throw new Error("final_output not found in trace");
  }
  return last;
}
