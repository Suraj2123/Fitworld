import { readdirSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

function files(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? files(path) : [path];
  });
}

const sources = ["fitworld/static", "tests/js", "scripts"]
  .flatMap(files)
  .filter((path) => /\.(m?js)$/.test(path));
for (const source of sources) {
  const result = spawnSync(process.execPath, ["--check", source], { stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
console.log(`JavaScript syntax checked: ${sources.length} files.`);
