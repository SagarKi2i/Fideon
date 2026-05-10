export type ClauseDiffStatus = "added" | "removed" | "changed";

export type PolicyClauseDiffClause = {
  id: string;
  title?: string;
  status: ClauseDiffStatus;
  before?: string;
  after?: string;
  path?: string;
};

export type PolicyClauseDiff = {
  clauses: PolicyClauseDiffClause[];
  meta?: Record<string, unknown>;
};

function stripCodeFences(input: string): string[] {
  const matches = input.match(/```(?:json)?\s*([\s\S]*?)\s*```/gi);
  return matches?.map((m: any) => m.replace(/```(?:json)?/i, "").replace(/```$/, "").trim()) ?? [];
}

function tryParseJson(candidate: string): unknown | null {
  try {
    return JSON.parse(candidate);
  } catch {
    return null;
  }
}

function extractJsonCandidates(input: string): string[] {
  const fenced = stripCodeFences(input);
  if (fenced.length > 0) return fenced;

  const firstBrace = input.indexOf("{");
  const lastBrace = input.lastIndexOf("}");
  if (firstBrace === -1 || lastBrace === -1 || lastBrace <= firstBrace) return [];
  return [input.slice(firstBrace, lastBrace + 1)];
}

function toMaybeString(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function normalizeStatus(value: unknown): ClauseDiffStatus | undefined {
  if (!value) return undefined;
  const v = String(value).toLowerCase().trim();
  if (["added", "add", "inserted", "new"].includes(v)) return "added";
  if (["removed", "remove", "deleted", "old"].includes(v)) return "removed";
  if (["changed", "change", "modified", "updated", "diff", "altered"].includes(v)) return "changed";
  return undefined;
}

function normalizeClauseStatus(item: any, before?: unknown, after?: unknown): ClauseDiffStatus {
  const explicit = normalizeStatus(item?.status ?? item?.change_type ?? item?.type);
  if (explicit) return explicit;

  const hasBefore = before !== undefined && before !== null && String(before).trim() !== "";
  const hasAfter = after !== undefined && after !== null && String(after).trim() !== "";
  if (hasBefore && !hasAfter) return "removed";
  if (!hasBefore && hasAfter) return "added";
  return "changed";
}

function normalizeId(item: any, fallbackId: number): string {
  const raw =
    item?.clause_id ??
    item?.id ??
    item?.key ??
    item?.path ??
    item?.title ??
    item?.name ??
    item?.heading;
  return raw !== undefined && raw !== null ? String(raw) : String(fallbackId);
}

function normalizeTitle(item: any): string | undefined {
  return toMaybeString(item?.title ?? item?.text ?? item?.heading ?? item?.name ?? item?.clause_text);
}

function normalizeBefore(item: any): string | undefined {
  return toMaybeString(
    item?.before ??
      item?.before_text ??
      item?.old ??
      item?.text_before ??
      item?.previous ??
      item?.removed_text ??
      item?.from,
  );
}

function normalizeAfter(item: any): string | undefined {
  return toMaybeString(
    item?.after ??
      item?.after_text ??
      item?.new ??
      item?.text_after ??
      item?.next ??
      item?.added_text ??
      item?.to,
  );
}

function normalizeFromArray(
  arr: any[],
  statusHint: ClauseDiffStatus,
): PolicyClauseDiffClause[] {
  return arr
    .map((item: any, idx: any) => {
      const before = normalizeBefore(item);
      const after = normalizeAfter(item);
      const status = statusHint ?? normalizeClauseStatus(item, before, after);

      return {
        id: normalizeId(item, idx),
        title: normalizeTitle(item),
        status,
        before,
        after,
        path: toMaybeString(item?.path ?? item?.field),
      } as PolicyClauseDiffClause;
    })
    .filter((c: any) => Boolean(c.id));
}

export function parsePolicyClauseDiff(input: string): PolicyClauseDiff | null {
  if (!input || !input.trim()) return null;

  const candidates = extractJsonCandidates(input);
  if (candidates.length === 0) return null;

  for (const candidate of candidates) {
    const parsed = tryParseJson(candidate);
    if (!parsed || typeof parsed !== "object") continue;

    const obj: any = parsed;
    let recognized = false;

    // Shape 1: { clauses: [...] }
    if (Array.isArray(obj?.clauses)) {
      recognized = true;
      const clauses: PolicyClauseDiffClause[] = obj.clauses
        .map((item: any, idx: number) => {
          const before = normalizeBefore(item);
          const after = normalizeAfter(item);
          const status = normalizeClauseStatus(item, before, after);
          return {
            id: normalizeId(item, idx),
            title: normalizeTitle(item),
            status,
            before,
            after,
            path: toMaybeString(item?.path ?? item?.field),
          } as PolicyClauseDiffClause;
        })
        .filter((c: PolicyClauseDiffClause) => Boolean(c.id));

      return { clauses, meta: obj?.meta ?? undefined };
    }

    // Shape 2: { added: [...], removed: [...], changed: [...] }
    if (Array.isArray(obj?.added) || Array.isArray(obj?.removed) || Array.isArray(obj?.changed)) {
      recognized = true;
      const clauses: PolicyClauseDiffClause[] = [
        ...(Array.isArray(obj?.added) ? normalizeFromArray(obj.added, "added") : []),
        ...(Array.isArray(obj?.removed) ? normalizeFromArray(obj.removed, "removed") : []),
        ...(Array.isArray(obj?.changed) ? normalizeFromArray(obj.changed, "changed") : []),
      ];
      return { clauses, meta: obj?.meta ?? undefined };
    }

    // Shape 3: { changes: [...] }
    if (Array.isArray(obj?.changes)) {
      recognized = true;
      const clauses: PolicyClauseDiffClause[] = obj.changes
        .map((item: any, idx: number) => {
          const before = normalizeBefore(item);
          const after = normalizeAfter(item);
          const status = normalizeClauseStatus(item, before, after);
          return {
            id: normalizeId(item, idx),
            title: normalizeTitle(item),
            status,
            before,
            after,
            path: toMaybeString(item?.path ?? item?.field),
          } as PolicyClauseDiffClause;
        })
        .filter((c: PolicyClauseDiffClause) => Boolean(c.id));

      return { clauses, meta: obj?.meta ?? undefined };
    }

    if (recognized) return { clauses: [], meta: obj?.meta ?? undefined };
  }

  return null;
}

