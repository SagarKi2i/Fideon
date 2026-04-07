declare module "mammoth/mammoth.browser" {
  export type ExtractRawTextResult = { value: string };

  export function extractRawText(args: { arrayBuffer: ArrayBuffer }): Promise<ExtractRawTextResult>;
}

