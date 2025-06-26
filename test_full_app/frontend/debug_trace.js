const fs = require('fs');
const path = require('path');

function extractFinalOutput(tracePath) {
  const data = fs.readFileSync(tracePath, "utf-8");
  let last = null;
  for (const line of data.split(/\r?\n/)) {
    if (!line.startsWith("data: ")) continue;
    try {
      const obj = JSON.parse(line.slice(6));
      if (Array.isArray(obj.ops)) {
        for (const op of obj.ops) {
          if (typeof op.path === "string" && op.path.endsWith("final_output")) {
            const val = op.value?.output || op.value;
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

const tracesDir = path.resolve(__dirname, "../traces");
const output = extractFinalOutput(path.join(tracesDir, "trace3.sse"));
console.log("Full expected output:");
console.log(output);
console.log("\nLast 20 characters:");
console.log(JSON.stringify(output.slice(-20))); 