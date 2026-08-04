#!/usr/bin/env node

import { chmod, mkdir, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const SERVICE_LABEL = "com.steedjson.semantic-model-router";
const pluginRoot = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const plistPath = path.join(os.homedir(), "Library", "LaunchAgents", `${SERVICE_LABEL}.plist`);
const maintenancePath = path.join(pluginRoot, "dist", "maintenance.js");
const dataDir = process.env.SEMANTIC_ROUTER_DATA_DIR ?? "";

function plistValue(value) {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

function renderPlist() {
  const environment = dataDir
    ? `\n    <key>SEMANTIC_ROUTER_DATA_DIR</key>\n    <string>${plistValue(dataDir)}</string>`
    : "";
  return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${SERVICE_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${plistValue(process.execPath)}</string>
    <string>${plistValue(maintenancePath)}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${plistValue(pluginRoot)}</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>0</integer>
    <key>Hour</key><integer>3</integer>
    <key>Minute</key><integer>0</integer>
  </dict>${environment}
  <key>RunAtLoad</key>
  <false/>
  <key>StandardOutPath</key>
  <string>/tmp/${SERVICE_LABEL}.out.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/${SERVICE_LABEL}.err.log</string>
</dict>
</plist>
`;
}

function requireMacOS() {
  if (process.platform !== "darwin") throw new Error("launchd maintenance is supported only on macOS");
}

function uid() {
  return String(process.getuid?.() ?? "");
}

async function install(dryRun) {
  requireMacOS();
  const content = renderPlist();
  if (dryRun) {
    process.stdout.write(`launchd plist ready: ${plistPath}\n`);
    process.stdout.write(content);
    return;
  }
  await mkdir(path.dirname(plistPath), { recursive: true, mode: 0o700 });
  await chmod(path.dirname(plistPath), 0o700);
  await writeFile(plistPath, content, { encoding: "utf8", mode: 0o600 });
  await chmod(plistPath, 0o600);
  execFileSync("launchctl", ["bootstrap", `gui/${uid()}`, plistPath], { stdio: "ignore" });
  process.stdout.write(`launchd maintenance installed: ${SERVICE_LABEL}\n`);
}

async function uninstall(dryRun) {
  requireMacOS();
  if (dryRun) {
    process.stdout.write(`launchd plist removal ready: ${plistPath}\n`);
    return;
  }
  try {
    execFileSync("launchctl", ["bootout", `gui/${uid()}`, plistPath], { stdio: "ignore" });
  } catch {
    // Service may already be unloaded; remove plist regardless.
  }
  await rm(plistPath, { force: true });
  process.stdout.write(`launchd maintenance removed: ${SERVICE_LABEL}\n`);
}

const command = process.argv[2] ?? "install";
const dryRun = process.argv.includes("--dry-run");
try {
  if (command === "install") await install(dryRun);
  else if (command === "uninstall") await uninstall(dryRun);
  else throw new Error("Usage: install-launchd.mjs [install|uninstall] [--dry-run]");
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
}
