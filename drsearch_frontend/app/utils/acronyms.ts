export interface ExpansionResult {
  text: string;
  acronym?: string;
  expansion?: string;
  start?: number;
}

export function expandLastAcronym(
  value: string,
  acronymMap: Record<string, string> = {},
): ExpansionResult {
  const match = value.match(/(\b\w+)\s$/);
  if (!match) {
    return { text: value };
  }
  const acronym = match[1];
  const expansion = acronymMap[acronym.toUpperCase()];
  if (!expansion) {
    return { text: value };
  }
  const start = match.index ?? value.length - acronym.length - 1;
  const replacedText = value.slice(0, start) + expansion + " ";
  return { text: replacedText, acronym, expansion, start };
}
