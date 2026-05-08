// Ambient declaration to satisfy TS import from src/integrations/supabase/client.ts
// This is a temporary shim; will be superseded when Supabase generates real types.
declare module "./types" {
  export type Database = any;
}
