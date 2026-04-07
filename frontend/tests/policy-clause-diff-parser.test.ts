import { describe, it, expect } from "vitest";
import { parsePolicyClauseDiff } from "@/lib/policyClauseDiff";

describe("policyClauseDiff parser", () => {
  it("parses fenced JSON { clauses: [...] } output", () => {
    const input = [
      "Some preamble text",
      "```json",
      JSON.stringify({
        clauses: [
          { clause_id: "c1", title: "Cyber Liability", status: "added", before: "", after: "Added clause text." },
        ],
      }),
      "```",
      "Trailing text",
    ].join("\n");

    const diff = parsePolicyClauseDiff(input);
    expect(diff).not.toBeNull();
    expect(diff?.clauses).toHaveLength(1);
    expect(diff?.clauses[0].id).toBe("c1");
    expect(diff?.clauses[0].title).toBe("Cyber Liability");
    expect(diff?.clauses[0].status).toBe("added");
    expect(diff?.clauses[0].after).toContain("Added clause text");
  });

  it("parses { added, removed, changed } shape", () => {
    const input = JSON.stringify({
      added: [{ id: "c2", title: "Employment Practices Liability", after: "Added EPLI clause." }],
      removed: [{ id: "c3", title: "Water Damage Exclusion", before: "Removed exclusion text." }],
      changed: [{ id: "c4", title: "Umbrella Coverage", before: "Old umbrella text", after: "New umbrella text", status: "changed" }],
    });

    const diff = parsePolicyClauseDiff(input);
    expect(diff).not.toBeNull();
    expect(diff?.clauses.map((c) => c.id)).toEqual(expect.arrayContaining(["c2", "c3", "c4"]));

    const c2 = diff?.clauses.find((c) => c.id === "c2");
    expect(c2?.status).toBe("added");
    expect(c2?.after).toContain("Added EPLI");

    const c3 = diff?.clauses.find((c) => c.id === "c3");
    expect(c3?.status).toBe("removed");
    expect(c3?.before).toContain("Removed exclusion");

    const c4 = diff?.clauses.find((c) => c.id === "c4");
    expect(c4?.status).toBe("changed");
    expect(c4?.before).toContain("Old umbrella");
    expect(c4?.after).toContain("New umbrella");
  });

  it("returns null when no JSON can be extracted", () => {
    const input = "No JSON here, only explanation.";
    const diff = parsePolicyClauseDiff(input);
    expect(diff).toBeNull();
  });
});

