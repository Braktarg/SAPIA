"use client";

export type BodyBlock =
  | { type: "heading"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; items: string[] };

/** Convierte el cuerpo de recomendación (markdown ligero) en bloques legibles. */
export function parseStudentBody(body: string): BodyBlock[] {
  const blocks: BodyBlock[] = [];
  let paragraphLines: string[] = [];
  let listItems: string[] = [];

  function flushParagraph() {
    const text = paragraphLines.join(" ").trim();
    if (text) blocks.push({ type: "paragraph", text });
    paragraphLines = [];
  }

  function flushList() {
    if (listItems.length > 0) {
      blocks.push({ type: "list", items: [...listItems] });
      listItems = [];
    }
  }

  for (const raw of body.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) {
      flushList();
      flushParagraph();
      continue;
    }

    const headingMatch = line.match(/^\*\*(.+)\*\*$/);
    if (headingMatch) {
      flushList();
      flushParagraph();
      blocks.push({ type: "heading", text: headingMatch[1] });
      continue;
    }

    const italicHeading = line.match(/^\*(.+)\*$/);
    if (italicHeading && !line.startsWith("* ")) {
      flushList();
      flushParagraph();
      blocks.push({ type: "heading", text: italicHeading[1] });
      continue;
    }

    if (line.startsWith("- ") || line.startsWith("• ")) {
      flushParagraph();
      listItems.push(line.replace(/^[-•]\s+/, "").replace(/\*\*/g, ""));
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      flushParagraph();
      listItems.push(line.replace(/^\d+\.\s+/, "").replace(/\*\*/g, ""));
      continue;
    }

    flushList();
    paragraphLines.push(line.replace(/\*\*/g, ""));
  }

  flushList();
  flushParagraph();
  return blocks;
}

type Props = {
  body: string;
};

export function StudentBodyBlocks({ body }: Props) {
  const blocks = parseStudentBody(body);
  if (blocks.length === 0) {
    return <div className="body-text student-body-blocks">{body}</div>;
  }

  return (
    <div className="student-body-blocks">
      {blocks.map((block, i) => {
        if (block.type === "heading") {
          return (
            <h4 key={i} className="student-block-heading">
              {block.text}
            </h4>
          );
        }
        if (block.type === "list") {
          return (
            <ul key={i} className="student-block-list">
              {block.items.map((item, j) => (
                <li key={j}>{item}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i} className="student-block-paragraph">
            {block.text}
          </p>
        );
      })}
    </div>
  );
}
