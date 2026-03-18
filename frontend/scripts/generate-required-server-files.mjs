import fs from "node:fs/promises";
import path from "node:path";

async function fileExists(p) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

async function main() {
  const projectRoot = path.resolve(process.cwd());
  const nextDir = path.join(projectRoot, ".next");
  const target = path.join(nextDir, "required-server-files.json");

  // Next should generate this when output=standalone, but some builds/configs
  // omit it. next-electron-rsc expects it to exist.
  if (await fileExists(target)) {
    return;
  }

  const content = {
    version: 1,
    config: {
      distDir: ".next",
      output: "standalone",
    },
  };

  await fs.mkdir(nextDir, { recursive: true });
  await fs.writeFile(target, JSON.stringify(content, null, 2), "utf8");
  // eslint-disable-next-line no-console
  console.log(`[postbuild] wrote ${path.relative(projectRoot, target)}`);
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error("[postbuild] failed to write required-server-files.json", err);
  process.exit(1);
});

