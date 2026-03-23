import { useCallback, useEffect, useRef } from "react";

/** Default aligns with common insurance / PHI session policies (15–20 min inactivity). */
const DEFAULT_MINUTES = 15;

/**
 * Returns idle duration in ms, or `null` if idle timeout is disabled (e.g. `NEXT_PUBLIC_IDLE_SESSION_MINUTES=0`).
 */
export function getIdleSessionTimeoutMs(): number | null {
  const raw = process.env.NEXT_PUBLIC_IDLE_SESSION_MINUTES;
  if (raw === undefined || raw === "") {
    return DEFAULT_MINUTES * 60 * 1000;
  }
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) {
    return null;
  }
  const clamped = Math.min(120, Math.max(5, Math.round(n)));
  return clamped * 60 * 1000;
}

/**
 * User activity that resets the inactivity timer (no `mousemove` — throttled via reset debounce).
 */
const ACTIVITY_EVENTS: (keyof WindowEventMap)[] = [
  "mousedown",
  "keydown",
  "scroll",
  "touchstart",
  "click",
  "wheel",
];

const THROTTLE_MS = 750;

/**
 * After `getIdleSessionTimeoutMs()` of no activity, invokes `onIdle` once.
 */
export function useIdleSessionTimeout(onIdle: () => void | Promise<void>, enabled: boolean) {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastResetRef = useRef(0);
  const onIdleRef = useRef(onIdle);
  onIdleRef.current = onIdle;

  const clearTimer = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  const schedule = useCallback(() => {
    clearTimer();
    const ms = getIdleSessionTimeoutMs();
    if (ms == null || !enabled) {
      return;
    }
    timeoutRef.current = setTimeout(() => {
      void Promise.resolve(onIdleRef.current());
    }, ms);
  }, [clearTimer, enabled]);

  const onActivity = useCallback(() => {
    const now = Date.now();
    if (now - lastResetRef.current < THROTTLE_MS) {
      return;
    }
    lastResetRef.current = now;
    schedule();
  }, [schedule]);

  useEffect(() => {
    if (!enabled) {
      clearTimer();
      return;
    }
    if (getIdleSessionTimeoutMs() == null) {
      return;
    }

    schedule();

    const opts: AddEventListenerOptions = { capture: true, passive: true };
    for (const ev of ACTIVITY_EVENTS) {
      window.addEventListener(ev, onActivity, opts);
    }

    return () => {
      clearTimer();
      for (const ev of ACTIVITY_EVENTS) {
        window.removeEventListener(ev, onActivity, opts);
      }
    };
  }, [enabled, schedule, onActivity, clearTimer]);
}
