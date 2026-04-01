import { createClient } from "@supabase/supabase-js";
import type { Database } from "./types";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL as string;
const SUPABASE_PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY as string;

const authLockNoOp: <R>(name: string, acquireTimeout: number, fn: () => Promise<R>) => Promise<R> = (
  _name,
  _acquireTimeout,
  fn,
) => fn();

const disableWebLocks =
  process.env.NODE_ENV === "development" ||
  process.env.NEXT_PUBLIC_SUPABASE_AUTH_NO_WEB_LOCKS === "true";

// Import the supabase client like this:
// import { supabase } from "@/integrations/supabase/client";

export const supabase = createClient<Database>(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
  auth: {
    storage: typeof window !== "undefined" ? localStorage : undefined,
    persistSession: true,
    autoRefreshToken: true,
    ...(disableWebLocks ? { lock: authLockNoOp } : {}),
  },
  realtime: {
    // Realtime disabled until permanent WSS URL is set up
    // @ts-expect-error
    url: null,
  },
});