export function convertToHttpUrlIfNeeded(filePath: string): string {
  console.debug("Original input:", filePath);

  // 1. Normalize all backslashes to forward slashes
  const normalized = filePath.replace(/\\/g, "/");
  console.debug("Normalized path:", normalized);

  // 2. Match UNC paths like \\home.drs.com@ssl\DavWWWRoot\...
  const uncMatch = normalized.match(/^\/\/?home\.drs\.com@ssl\/DavWWWRoot\/(.+)/i);
  if (uncMatch) {
    console.debug("Matched UNC path");
    const encodedPath = encodeURI(uncMatch[1]);
    const finalUrl = `https://home.drs.com/${encodedPath}?web=1`;
    console.debug("Converted UNC URL:", finalUrl);
    return finalUrl;
  }

  // 3. Match SEPS_DOCS paths like SEPS_DOCS/docs/…
  const sepsMatch = normalized.match(/^SEPS_DOCS\/docs\/(.+)/i);
  if (sepsMatch) {
    console.debug("Matched SEPS_DOCS path");
    const encodedPath = encodeURI(sepsMatch[1]);
    const finalUrl = `https://company.sharepoint.us/sites/SEPs/${encodedPath}.docx?web=1`;
    console.debug("Converted SEPS_DOCS URL:", finalUrl);
    return finalUrl;
  }

  // 4. If nothing matched, return the original
  console.debug("No match found. Returning original path.");
  return filePath;
}
