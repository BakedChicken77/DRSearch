import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(__dirname, "../drsearch_frontend");
const e2eSpecPath = path.resolve(frontendDir, "testing_full_app/e2e.spec.ts");
const e2eNegativeSpecPath = path.resolve(frontendDir, "testing_full_app/e2e_negative.spec.ts");

function log(message, level = "INFO") {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [${level}] ${message}`);
}

function toggleSkippedTests(enable = false) {
  log(`Toggling skipped tests: ${enable ? 'ENABLE' : 'DISABLE'}`);
  
  // Toggle e2e.spec.ts
  if (fs.existsSync(e2eSpecPath)) {
    let content = fs.readFileSync(e2eSpecPath, "utf8");
    const originalLine = "const t = idx === 2 ? test.skip : test;";
    const enabledLine = "const t = test; // Temporarily enabled for debugging";
    const disabledLine = "const t = idx === 2 ? test.skip : test; // TODO: Investigate why payload 3 is being skipped";
    
    if (enable) {
      content = content.replace(originalLine, enabledLine);
      log("Enabled payload 3 test in e2e.spec.ts", "INFO");
    } else {
      content = content.replace(enabledLine, disabledLine);
      log("Disabled payload 3 test in e2e.spec.ts", "INFO");
    }
    
    fs.writeFileSync(e2eSpecPath, content);
  }
  
  // Toggle e2e_negative.spec.ts
  if (fs.existsSync(e2eNegativeSpecPath)) {
    let content = fs.readFileSync(e2eNegativeSpecPath, "utf8");
    const originalLine = "test.describe.skip(\"negative scenarios\", () => {";
    const enabledLine = "test.describe(\"negative scenarios\", () => { // Temporarily enabled for debugging";
    const disabledLine = "test.describe.skip(\"negative scenarios\", () => { // TODO: Investigate why negative scenarios are being skipped";
    
    if (enable) {
      content = content.replace(originalLine, enabledLine);
      log("Enabled negative scenarios in e2e_negative.spec.ts", "INFO");
    } else {
      content = content.replace(enabledLine, disabledLine);
      log("Disabled negative scenarios in e2e_negative.spec.ts", "INFO");
    }
    
    fs.writeFileSync(e2eNegativeSpecPath, content);
  }
  
  log("Test toggle completed", "INFO");
}

function main() {
  const args = process.argv.slice(2);
  const command = args[0];
  
  if (command === "enable") {
    toggleSkippedTests(true);
  } else if (command === "disable") {
    toggleSkippedTests(false);
  } else {
    log("Usage: node toggle-skipped-tests.mjs [enable|disable]", "ERROR");
    log("  enable  - Enable all skipped tests for debugging", "INFO");
    log("  disable - Disable tests back to original state", "INFO");
    process.exit(1);
  }
}

main(); 