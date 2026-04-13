import { createClient } from "@supabase/supabase-js";

import type { Database } from "./types";
 
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL as string;

const SUPABASE_PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY as string;
 
/**

* Supabase Auth defaults to navigator.locks in the browser. Concurrent calls

* (React Strict Mode, Fast Refresh, parallel getSession) can abort with:

* AbortError: Lock broken by another request with the 'steal' option.

* A no-op lock disables cross-tab Web Locks in dev; production keeps the default.

*/

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

});
 