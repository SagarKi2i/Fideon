/**
 * Named pipe server — lets the Electron UI communicate with the Windows service.
 * Protocol: newline-delimited JSON over \\.\pipe\FideonOSService.
 *
 * Accepted request types:
 *   { "type": "status" }   → returns ServiceStatus
 *   { "type": "reauth" }   → reloads credentials from ProgramData, returns updated status
 *   { "type": "stop" }     → graceful shutdown
 */
import net from "node:net";
import { PIPE_PATH, serviceClient } from "./service-client";

export type PipeRequest = { type: "status" | "reauth" | "stop" };

let server: net.Server | null = null;

export function startPipeServer(log: (msg: string) => void): net.Server {
  server = net.createServer((socket) => {
    let buffer = "";

    socket.on("data", (chunk) => {
      buffer += chunk.toString("utf8");
      let nl: number;
      while ((nl = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (!line) continue;
        try {
          const req = JSON.parse(line) as PipeRequest;
          handleRequest(req, socket, log);
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          socket.write(JSON.stringify({ ok: false, error: `Invalid JSON: ${msg}` }) + "\n");
        }
      }
    });

    socket.on("error", () => {
      // client disconnected abruptly — ignore
    });
  });

  server.listen(PIPE_PATH, () => {
    log(`[service-ipc] listening at ${PIPE_PATH}`);
  });

  server.on("error", (err) => {
    log(`[service-ipc] server error: ${err.message}`);
  });

  return server;
}

function handleRequest(req: PipeRequest, socket: net.Socket, log: (msg: string) => void): void {
  switch (req.type) {
    case "status": {
      socket.write(JSON.stringify({ ok: true, ...serviceClient.getStatus() }) + "\n");
      break;
    }
    case "reauth": {
      serviceClient.reloadCredentials();
      socket.write(JSON.stringify({ ok: true, reloaded: true, ...serviceClient.getStatus() }) + "\n");
      log(`[service-ipc] credentials reloaded via pipe`);
      break;
    }
    case "stop": {
      socket.write(JSON.stringify({ ok: true, stopping: true }) + "\n");
      log(`[service-ipc] stop requested via pipe`);
      setImmediate(() => process.exit(0));
      break;
    }
    default: {
      socket.write(JSON.stringify({ ok: false, error: "Unknown request type" }) + "\n");
    }
  }
}

export function stopPipeServer(): void {
  server?.close();
  server = null;
}
