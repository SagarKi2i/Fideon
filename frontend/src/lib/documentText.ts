export type ExtractedDocumentText = {
  filename: string;
  mimeType: string;
  text: string;
  pageCount?: number;
};

function normalizeWhitespace(input: string): string {
  return input
    .replace(/\r\n/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

async function extractPdfText(file: File): Promise<ExtractedDocumentText> {
  // Lazy-load to avoid increasing initial bundle size.
  const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");

  // Configure worker as a URL asset so bundlers don't try to parse/minify it.
  const workerUrl = (await import("pdfjs-dist/legacy/build/pdf.worker.min.mjs?url")).default as string;
  (pdfjs as unknown as { GlobalWorkerOptions: { workerSrc: string } }).GlobalWorkerOptions.workerSrc = workerUrl;

  const bytes = new Uint8Array(await file.arrayBuffer());
  const loadingTask = (pdfjs as unknown as { getDocument: (args: unknown) => { promise: Promise<unknown> } }).getDocument({
    data: bytes,
  });
  const pdf = (await loadingTask.promise) as { numPages?: number; getPage: (n: number) => Promise<unknown> };

  const maxPages = Math.min(Number(pdf.numPages ?? 0) || 0, 60);
  const chunks: string[] = [];
  for (let i = 1; i <= maxPages; i++) {
    const page = (await pdf.getPage(i)) as { getTextContent: () => Promise<unknown> };
    const content = (await page.getTextContent()) as { items?: Array<{ str?: unknown }> };
    const pageText = (content.items ?? [])
      .map((it: any) => String(it?.str ?? ""))
      .filter(Boolean)
      .join(" ");
    if (pageText.trim()) chunks.push(pageText);
  }

  return {
    filename: file.name,
    mimeType: file.type || "application/pdf",
    pageCount: Number(pdf.numPages ?? maxPages) || maxPages,
    text: normalizeWhitespace(chunks.join("\n\n")),
  };
}

async function extractDocxText(file: File): Promise<ExtractedDocumentText> {
  const mammoth = await import("mammoth/mammoth.browser");
  const arrayBuffer = await file.arrayBuffer();
  const result = await mammoth.extractRawText({ arrayBuffer });
  return {
    filename: file.name,
    mimeType: file.type || "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    text: normalizeWhitespace(result.value || ""),
  };
}

async function extractPlainText(file: File): Promise<ExtractedDocumentText> {
  const text = await file.text();
  return { filename: file.name, mimeType: file.type || "text/plain", text: normalizeWhitespace(text) };
}

export async function extractDocumentText(file: File): Promise<ExtractedDocumentText> {
  const name = file.name.toLowerCase();
  const type = (file.type || "").toLowerCase();

  if (type.includes("pdf") || name.endsWith(".pdf")) return extractPdfText(file);
  if (type.includes("wordprocessingml") || name.endsWith(".docx")) return extractDocxText(file);
  if (type.startsWith("text/") || name.endsWith(".txt") || name.endsWith(".md")) return extractPlainText(file);

  // Best-effort fallback: try reading as text (some uploads have missing mime types).
  return extractPlainText(file);
}

