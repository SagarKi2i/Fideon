/**
 * Webhook IPC bridge tests (FNF-195)
 *
 * Covers every public function in webhooksApi.ts for two execution paths:
 *   1. Electron IPC  — window.electron.webhooks.* is present
 *   2. HTTP fallback — window.electron is absent (browser / web mode)
 *
 * Mocks: supabase session, apiUrl, httpErrors helpers, and global fetch.
 */

import { describe, it, expect, vi, afterEach } from "vitest";

// ── module mocks (hoisted before imports) ─────────────────────────────────────

vi.mock("@/integrations/supabase/client", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { access_token: "tok-test" } },
      }),
    },
  },
}));

vi.mock("@/lib/apiBaseUrl", () => ({
  apiUrl: (p: string) => `http://localhost:8000${p}`,
}));

vi.mock("@/lib/httpErrors", () => ({
  buildApiRequestError: (_res: Response, payload: unknown, msg: string) =>
    new Error(`${msg}: ${JSON.stringify(payload)}`),
  notAuthenticatedError: () => new Error("Not authenticated"),
  readJsonSafe: async (res: Response) => {
    try {
      return await res.json();
    } catch {
      return {};
    }
  },
}));

import {
  createWebhook,
  deleteWebhook,
  fetchWebhooks,
  rotateWebhookSecret,
  sendTestEvent,
  updateWebhook,
  type WebhookRow,
} from "@/lib/webhooksApi";

// ── shared fixtures ───────────────────────────────────────────────────────────

const TOKEN = "tok-test";

const MOCK_WEBHOOK: WebhookRow = {
  id: "wh-1",
  tenant_id: "t-1",
  url: "https://example.com/hook",
  description: "Test webhook",
  events: ["device.online"],
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function mockFetch(payload: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    json: async () => payload,
  } as unknown as Response);
}

function mountIpc(handlers: Record<string, ReturnType<typeof vi.fn>>) {
  (window as Record<string, unknown>).electron = { webhooks: handlers };
}

afterEach(() => {
  delete (window as Record<string, unknown>).electron;
  vi.restoreAllMocks();
});

// ── fetchWebhooks ─────────────────────────────────────────────────────────────

describe("fetchWebhooks", () => {
  it("IPC: calls list() with access token and returns webhook rows", async () => {
    const list = vi.fn().mockResolvedValue({ success: true, webhooks: [MOCK_WEBHOOK] });
    mountIpc({ list });

    const result = await fetchWebhooks();

    expect(list).toHaveBeenCalledOnce();
    expect(list).toHaveBeenCalledWith(TOKEN);
    expect(result).toEqual([MOCK_WEBHOOK]);
  });

  it("IPC: throws when success=false", async () => {
    mountIpc({ list: vi.fn().mockResolvedValue({ success: false, error: "DB error" }) });

    await expect(fetchWebhooks()).rejects.toThrow("DB error");
  });

  it("HTTP: GET /api/v1/webhooks with Authorization header", async () => {
    global.fetch = mockFetch({ webhooks: [MOCK_WEBHOOK] });

    const result = await fetchWebhooks();

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/webhooks",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${TOKEN}` }),
      }),
    );
    expect(result).toEqual([MOCK_WEBHOOK]);
  });

  it("HTTP: throws on non-ok response", async () => {
    global.fetch = mockFetch({ error: "Unauthorized" }, false, 401);

    await expect(fetchWebhooks()).rejects.toThrow("Failed to load webhooks");
  });
});

// ── createWebhook ─────────────────────────────────────────────────────────────

describe("createWebhook", () => {
  const INPUT = { url: "https://example.com/hook", description: "Test", events: ["device.online"] };
  const RESPONSE = { webhook: MOCK_WEBHOOK, secret: "s3cr3t-val", note: "Copy now" };

  it("IPC: calls create() with token + input and returns webhook and secret", async () => {
    const create = vi.fn().mockResolvedValue({ success: true, ...RESPONSE });
    mountIpc({ create });

    const result = await createWebhook(INPUT);

    expect(create).toHaveBeenCalledWith(TOKEN, INPUT);
    expect(result.webhook).toEqual(MOCK_WEBHOOK);
    expect(result.secret).toBe("s3cr3t-val");
  });

  it("IPC: throws when success=false", async () => {
    mountIpc({
      create: vi.fn().mockResolvedValue({ success: false, error: "Forbidden" }),
    });

    await expect(createWebhook(INPUT)).rejects.toThrow("Forbidden");
  });

  it("HTTP: POST /api/v1/webhooks with serialized body", async () => {
    global.fetch = mockFetch(RESPONSE);

    const result = await createWebhook(INPUT);

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/webhooks",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ url: INPUT.url, description: INPUT.description, events: INPUT.events }),
      }),
    );
    expect(result.secret).toBe("s3cr3t-val");
  });

  it("HTTP: throws on non-ok response", async () => {
    global.fetch = mockFetch({ error: "Invalid URL" }, false, 400);

    await expect(createWebhook(INPUT)).rejects.toThrow("Failed to create webhook");
  });
});

// ── updateWebhook ─────────────────────────────────────────────────────────────

describe("updateWebhook", () => {
  it("IPC: calls update() with token, id, and patch", async () => {
    const update = vi.fn().mockResolvedValue({ success: true });
    mountIpc({ update });

    await updateWebhook("wh-1", { is_active: false });

    expect(update).toHaveBeenCalledWith(TOKEN, "wh-1", { is_active: false });
  });

  it("IPC: throws when success=false", async () => {
    mountIpc({
      update: vi.fn().mockResolvedValue({ success: false, error: "Not found" }),
    });

    await expect(updateWebhook("wh-1", { is_active: false })).rejects.toThrow("Not found");
  });

  it("HTTP: PATCH /api/v1/webhooks/:id with patch body", async () => {
    global.fetch = mockFetch({ success: true });

    await updateWebhook("wh-1", { is_active: false });

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/webhooks/wh-1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ is_active: false }),
      }),
    );
  });
});

// ── deleteWebhook ─────────────────────────────────────────────────────────────

describe("deleteWebhook", () => {
  it("IPC: calls delete() with token and id", async () => {
    const del = vi.fn().mockResolvedValue({ success: true });
    mountIpc({ delete: del });

    await deleteWebhook("wh-1");

    expect(del).toHaveBeenCalledWith(TOKEN, "wh-1");
  });

  it("IPC: throws when success=false", async () => {
    mountIpc({
      delete: vi.fn().mockResolvedValue({ success: false, error: "Forbidden" }),
    });

    await expect(deleteWebhook("wh-1")).rejects.toThrow("Forbidden");
  });

  it("HTTP: DELETE /api/v1/webhooks/:id", async () => {
    global.fetch = mockFetch({ success: true });

    await deleteWebhook("wh-1");

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/webhooks/wh-1",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});

// ── rotateWebhookSecret ───────────────────────────────────────────────────────

describe("rotateWebhookSecret", () => {
  it("IPC: calls rotateSecret() and returns new secret", async () => {
    const rotateSecret = vi.fn().mockResolvedValue({
      success: true,
      secret: "new-s3cr3t",
      note: "Copy now",
    });
    mountIpc({ rotateSecret });

    const result = await rotateWebhookSecret("wh-1");

    expect(rotateSecret).toHaveBeenCalledWith(TOKEN, "wh-1");
    expect(result.secret).toBe("new-s3cr3t");
  });

  it("IPC: throws when success=false", async () => {
    mountIpc({
      rotateSecret: vi.fn().mockResolvedValue({ success: false, error: "Rotation failed" }),
    });

    await expect(rotateWebhookSecret("wh-1")).rejects.toThrow("Rotation failed");
  });

  it("HTTP: POST /api/v1/webhooks/:id/rotate-secret", async () => {
    global.fetch = mockFetch({ secret: "new-s3cr3t", note: "Copy now" });

    const result = await rotateWebhookSecret("wh-1");

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/webhooks/wh-1/rotate-secret",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.secret).toBe("new-s3cr3t");
  });
});

// ── sendTestEvent ─────────────────────────────────────────────────────────────

describe("sendTestEvent", () => {
  it("IPC: calls testEvent() with token, event type, and payload", async () => {
    const testEvent = vi.fn().mockResolvedValue({ success: true, event_id: "ev-abc" });
    mountIpc({ testEvent });

    const result = await sendTestEvent("device.online", { source: "manual_test" });

    expect(testEvent).toHaveBeenCalledWith(TOKEN, "device.online", { source: "manual_test" });
    expect(result.event_id).toBe("ev-abc");
  });

  it("IPC: throws when success=false", async () => {
    mountIpc({
      testEvent: vi.fn().mockResolvedValue({ success: false, error: "Tenant required" }),
    });

    await expect(sendTestEvent("device.online")).rejects.toThrow("Tenant required");
  });

  it("HTTP: POST /api/v1/webhooks/test-event with event_type and payload", async () => {
    global.fetch = mockFetch({ success: true, event_id: "ev-abc" });

    const result = await sendTestEvent("model.deployed", { source: "manual_test" });

    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/webhooks/test-event",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ event_type: "model.deployed", payload: { source: "manual_test" } }),
      }),
    );
    expect(result.event_id).toBe("ev-abc");
  });

  it("HTTP: defaults payload to {} when omitted", async () => {
    global.fetch = mockFetch({ success: true, event_id: "ev-xyz" });

    await sendTestEvent("inference.complete");

    const call = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(call[1].body as string) as { event_type: string; payload: unknown };
    expect(body.event_type).toBe("inference.complete");
    expect(body.payload).toEqual({});
  });

  it("HTTP: throws on non-ok response", async () => {
    global.fetch = mockFetch({ error: "Tenant required" }, false, 403);

    await expect(sendTestEvent("device.online")).rejects.toThrow("Failed to send test event");
  });
});
