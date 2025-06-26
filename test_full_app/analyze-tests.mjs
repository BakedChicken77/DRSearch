import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(__dirname, "../drsearch_frontend");
const testDir = path.resolve(frontendDir, "test_full_app/frontend");

function log(message, level = "INFO") {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [${level}] ${message}`);
}

function analyzeTestFile(filePath) {
  log(`Analyzing test file: ${filePath}`);
  
  if (!fs.existsSync(filePath)) {
    log(`File not found: ${filePath}`, "ERROR");
    return;
  }
  
  const content = fs.readFileSync(filePath, "utf8");
  const lines = content.split("\n");
  
  let testCount = 0;
  let skippedTestCount = 0;
  let describeSkipCount = 0;
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    
    // Check for test.describe.skip
    if (line.includes("test.describe.skip")) {
      describeSkipCount++;
      log(`Found skipped test suite at line ${i + 1}: ${line}`, "WARN");
    }
    
    // Check for test.skip
    if (line.includes("test.skip")) {
      skippedTestCount++;
      log(`Found skipped test at line ${i + 1}: ${line}`, "WARN");
    }
    
    // Check for regular tests
    if (line.startsWith("test(") || line.startsWith("test(`") || line.startsWith('test("')) {
      testCount++;
      log(`Found test at line ${i + 1}: ${line}`, "INFO");
    }
  }
  
  log(`Test file summary for ${path.basename(filePath)}:`, "INFO");
  log(`  Total tests found: ${testCount}`, "INFO");
  log(`  Skipped tests: ${skippedTestCount}`, "WARN");
  log(`  Skipped test suites: ${describeSkipCount}`, "WARN");
  
  return { testCount, skippedTestCount, describeSkipCount };
}

function main() {
  log("Starting test analysis...");
  
  const testFiles = [
    path.join(testDir, "e2e.spec.ts"),
    path.join(testDir, "e2e_negative.spec.ts")
  ];
  
  let totalTests = 0;
  let totalSkipped = 0;
  let totalSkippedSuites = 0;
  
  testFiles.forEach(file => {
    const result = analyzeTestFile(file);
    if (result) {
      totalTests += result.testCount;
      totalSkipped += result.skippedTestCount;
      totalSkippedSuites += result.describeSkipCount;
    }
    console.log(""); // Empty line for readability
  });
  
  log("=== SUMMARY ===", "INFO");
  log(`Total tests across all files: ${totalTests}`, "INFO");
  log(`Total skipped tests: ${totalSkipped}`, "WARN");
  log(`Total skipped test suites: ${totalSkippedSuites}`, "WARN");
  
  // Explain the skip reasons based on our analysis
  log("=== SKIP REASONS ===", "INFO");
  log("1. In e2e.spec.ts: Line 23 uses 'test.skip' for payload 3 (idx === 2)", "INFO");
  log("2. In e2e_negative.spec.ts: Line 25 uses 'test.describe.skip' for entire negative scenarios suite", "INFO");
  log("Total expected skipped tests: 4 (1 from e2e.spec.ts + 3 from e2e_negative.spec.ts)", "INFO");
}

main(); 