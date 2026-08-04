import { chmod, mkdir, rm } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import { build } from "esbuild";

const root = process.cwd();
const dist = path.join(root, "dist");
await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });

const shared = {
  bundle: true,
  format: "esm",
  platform: "node",
  target: "node22",
  sourcemap: false,
  minify: false,
  legalComments: "none",
  metafile: true,
};

const serverBuild = await build({
  ...shared,
  entryPoints: [path.join(root, "src/server.ts")],
  outfile: path.join(dist, "server.js"),
});
assertNoExternalPackages(serverBuild.metafile);

const maintenanceBuild = await build({
  ...shared,
  entryPoints: [path.join(root, "src/maintenance.ts")],
  outfile: path.join(dist, "maintenance.js"),
});
assertNoExternalPackages(maintenanceBuild.metafile);

const hookOutput = path.join(root, "hooks/user-prompt-submit.mjs");
const hookBuild = await build({
  ...shared,
  entryPoints: [path.join(root, "src/hook.ts")],
  outfile: hookOutput,
  banner: { js: "#!/usr/bin/env node" },
});
assertNoExternalPackages(hookBuild.metafile);
await chmod(hookOutput, 0o755);

function assertNoExternalPackages(metafile) {
  for (const output of Object.values(metafile.outputs)) {
    const external = output.imports.filter(
      (item) => item.external && !item.path.startsWith("node:"),
    );
    if (external.length) {
      throw new Error(
        `bundle contains external runtime imports: ${external.map((item) => item.path).join(", ")}`,
      );
    }
  }
}
