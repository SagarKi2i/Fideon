/**
 * next-electron-rsc registers protocol.handle("http") and rejects any URL that is not the Next
 * dev server origin, which breaks renderer fetches to FastAPI (e.g. http://localhost:8001).
 * Forward those requests with electron.net.fetch instead.
 */
const fs = require("node:fs");
const path = require("node:path");

const target = path.join(
  __dirname,
  "..",
  "node_modules",
  "next-electron-rsc",
  "build",
  "index.js",
);

const marker = "/* fideon: http passthrough for FastAPI */";
const requireLine = 'const electron_1 = require("electron");';

function patch() {
  if (!fs.existsSync(target)) {
    console.warn("[patch-next-electron-rsc] skip: file not found:", target);
    return;
  }
  let s = fs.readFileSync(target, "utf8");
  if (s.includes(marker)) return;

  const oldAssert =
    "(0, node_assert_1.default)(request.url.startsWith(localhostUrl), 'External HTTP not supported, use HTTPS');";
  if (!s.includes(oldAssert)) {
    console.warn("[patch-next-electron-rsc] skip: expected assert line missing (already patched or version mismatch)");
    return;
  }

  if (!s.includes('const cookie_1 = require("cookie");')) {
    console.warn("[patch-next-electron-rsc] skip: unexpected file layout");
    return;
  }

  s = s.replace(
    'const cookie_1 = require("cookie");\n',
    `const cookie_1 = require("cookie");\n${requireLine} ${marker}\n`,
  );
  s = s.replace(
    oldAssert,
    `// Passthrough non-Next HTTP (FastAPI, etc.) — see electron/scripts/patch-next-electron-rsc.cjs
                    if (!request.url.startsWith(localhostUrl)) {
                        return yield electron_1.net.fetch(request);
                    }`,
  );
  fs.writeFileSync(target, s, "utf8");
  console.log("[patch-next-electron-rsc] applied");
}

patch();
