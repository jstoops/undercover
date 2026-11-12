import type { Step } from "./api";
import { documentName, sectionsRead } from "./steps";

export function SectionsRead({ steps }: Readonly<{ steps: Step[] }>) {
  const read = sectionsRead(steps);
  return (
    <section className="panel" aria-labelledby="read-heading">
      <h2 id="read-heading">What the agent read</h2>
      {read.length === 0 ? (
        <p>Nothing yet.</p>
      ) : (
        <ul className="sections-read" aria-label="Sections read">
          {read.map((section) => (
            <li key={`${section.document} ${String(section.number)}`}>
              {documentName(section.document)},{" "}
              <span className="mono">{section.number}.</span> {section.title}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
