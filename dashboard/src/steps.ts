import type { Step } from "./api";

export const DOCUMENT_NAMES: Partial<Record<string, string>> = {
  "policy-wording": "Policy wording",
  "claims-manual": "Claims manual",
};

export interface SectionRead {
  document: string;
  number: number;
  title: string;
}

/** A step's content as JSON, or the text itself when it isn't JSON. */
export function parse(content: string): unknown {
  try {
    return JSON.parse(content);
  } catch {
    return content;
  }
}

/** One field of a JSON object, or undefined. */
export function field(value: unknown, key: string): unknown {
  return typeof value === "object" && value !== null && key in value
    ? (value as Record<string, unknown>)[key]
    : undefined;
}

/** A document's name, such as "Claims manual". */
export function documentName(document: unknown): string {
  return (
    (typeof document === "string" ? DOCUMENT_NAMES[document] : undefined) ??
    "Document"
  );
}

function sectionIn(step: Step): SectionRead | null {
  if (step.kind !== "tool_result" || step.name !== "read_section") return null;
  const value = parse(step.content);
  const document = field(value, "document");
  const number = field(value, "number");
  const title = field(value, "title");
  return typeof document === "string" &&
    typeof number === "number" &&
    typeof title === "string"
    ? { document, number, title }
    : null;
}

/** The sections the agent read, once each, in the order it read them. */
export function sectionsRead(steps: Step[]): SectionRead[] {
  const read = new Map<string, SectionRead>();
  for (const section of steps.map(sectionIn)) {
    const key = `${section?.document ?? ""} ${String(section?.number)}`;
    if (section && !read.has(key)) read.set(key, section);
  }
  return [...read.values()];
}
