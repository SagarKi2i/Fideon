/**
 * electron-builder fails with "Access is denied" when clearing release/win-unpacked
 * if Fideon OS (or Electron from that folder) still has DLLs loaded.
 */
const { execSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const winUnpacked = path.join(__dirname, "..", "release", "win-unpacked");

function sleepSync(ms) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    /* wait for handles to release after taskkill */
  }
}

if (process.platform === "win32") {
  for (const im of ["Fideon OS.exe", "electron.exe"]) {
    try {
      execSync(`taskkill /IM "${im}" /F`, { stdio: "ignore" });
    } catch {
      /* not running */
    }
  }
  sleepSync(1500);
}

if (!fs.existsSync(winUnpacked)) {
  process.exit(0);
}

let lastErr;
for (let attempt = 0; attempt < 6; attempt++) {
  try {
    fs.rmSync(winUnpacked, { recursive: true, force: true });
    console.log("[pre-dist] removed release/win-unpacked");
    process.exit(0);
  } catch (err) {
    lastErr = err;
    sleepSync(500);
  }
}
console.error(
  "[pre-dist] Could not remove release/win-unpacked. Quit Fideon OS (and any Electron from win-unpacked), close Explorer on that folder, then retry.\n",
  lastErr && lastErr.message,
);
process.exit(1);
