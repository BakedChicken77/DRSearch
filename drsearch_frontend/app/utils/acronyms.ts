export const ACRONYM_MAP: Record<string, string> = {
  HR: "Human Resources",
  IT: "Information Technology",
  FAQ: "Frequently Asked Questions",
};

export interface ExpansionResult {
  text: string;
  acronym?: string;
  expansion?: string;
}

export function expandLastAcronym(value: string): ExpansionResult {
  const match = value.match(/(\b\w+)\s$/);
  if (!match) {
    return { text: value };
  }
  const acronym = match[1];
  const expansion = ACRONYM_MAP[acronym.toUpperCase()];
  if (!expansion) {
    return { text: value };
  }
  const replacedText = value.slice(0, -acronym.length - 1) + expansion + " ";
  return { text: replacedText, acronym, expansion };
}
