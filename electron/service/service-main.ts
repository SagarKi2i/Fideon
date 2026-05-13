/**
 * Windows service entry point.
 * Registered via node-windows as "FideonOS Device Service".
 * Runs as SYSTEM; no Electron or GUI dependencies.
 *
 * Lifecycle:
 *   1. node-windows spawns this script via node.exe
 *   2. We start the named pipe server and heartbeat loop
 *   3. SCM stop → SIGTERM → graceful shutdown
 */
import path from "node:path";
import fs from "node:fs";
import { serviceClient } from "./service-client";
import { startPipeServer, stopPipeServer } from "./service-ipc";

const LOG_DIR = path.join("C:\\ProgramData", "FideonOS", "logs");
const LOG_FILE = path.join(LOG_DIR, "service.log");

function log(msg: string): void {
  const line = `${new Date().toISOString()} ${msg}\n`;
  process.stdout.write(line);
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    fs.appendFileSync(LOG_FILE, line, "utf8");
  } catch {
    // ignore logging failures
  }
}

function shutdown(): void {
  log("[service] shutdown requested");
  stopPipeServer();
  serviceClient.stop();
  process.exit(0);
}

process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);

// node-windows may send IPC "shutdown" message when SCM requests service stop
process.on("message", (msg) => {
  if (msg === "shutdown") shutdown();
});

process.on("uncaughtException", (err) => {
  log(`[service] uncaughtException: ${err.message}\n${err.stack ?? ""}`);
});

process.on("unhandledRejection", (reason) => {
  const msg = reason instanceof Error ? reason.message : String(reason);
  log(`[service] unhandledRejection: ${msg}`);
});

log("[service] FideonOS Device Service starting");
startPipeServer(log);
serviceClient.start();
log("[service] FideonOS Device Service ready");
