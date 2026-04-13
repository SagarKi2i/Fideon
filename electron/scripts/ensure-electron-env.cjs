/**
 * Ensures electron/.env exists before electron-builder packs extraResources.
 * QA builds overwrite .env with the target API URL; local dist uses this default.
 */
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const envPath = path.join(root, ".env");
const examplePath = path.join(root, ".env.example");

if (!fs.existsSync(envPath)) {
  if (!fs.existsSync(examplePath)) {
    console.error("[ensure-electron-env] Missing .env.example");
    process.exit(1);
  }
  fs.copyFileSync(examplePath, envPath);
  console.log("[ensure-electron-env] created electron/.env from .env.example");
}
