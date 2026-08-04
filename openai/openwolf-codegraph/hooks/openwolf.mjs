import * as fs from 'node:fs';
import * as path from 'node:path';
import { spawnSync } from 'node:child_process';

const mode = process.argv[2] || '';

async function readHookInput() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString('utf-8').trim();
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function directoryCandidate(value) {
  if (typeof value !== 'string' || !value.trim()) return null;
  const resolved = path.resolve(value);
  try {
    return fs.statSync(resolved).isDirectory() ? resolved : path.dirname(resolved);
  } catch {
    return resolved;
  }
}

function findProjectRoot(input) {
  const explicitCandidates = [
    input.cwd,
    input.project_dir,
    input.workspace_root,
  ].filter((candidate) => directoryCandidate(candidate));
  const fallbackCandidates = [
    process.env.CODEX_PROJECT_DIR,
    process.env.CLAUDE_PROJECT_DIR,
    process.env.PWD,
    process.cwd(),
  ];
  const candidates = explicitCandidates.length > 0
    ? explicitCandidates
    : fallbackCandidates;

  for (const candidate of candidates) {
    let current = directoryCandidate(candidate);
    if (!current) continue;
    while (true) {
      if (
        fs.existsSync(path.join(current, '.wolf')) ||
        fs.existsSync(path.join(current, '.codegraph')) ||
        fs.existsSync(path.join(current, '.git'))
      ) {
        return current;
      }
      const parent = path.dirname(current);
      if (parent === current) break;
      current = parent;
    }
  }
  return null;
}

function runOpenWolfHook(projectRoot, scriptName, payload) {
  const hookPath = path.join(projectRoot, '.wolf', 'hooks', scriptName);
  if (!fs.existsSync(hookPath)) return;
  const result = spawnSync(process.execPath, [hookPath], {
    cwd: projectRoot,
    env: {
      ...process.env,
      CLAUDE_PROJECT_DIR: projectRoot,
      CODEX_PROJECT_DIR: projectRoot,
    },
    input: JSON.stringify(payload || {}),
    encoding: 'utf-8',
    timeout: 15000,
  });
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  if (result.error) {
    process.stderr.write(`OpenWolf hook error: ${result.error.message}\n`);
  }
}

function getToolInput(input) {
  const toolInput = input.tool_input ?? input.toolInput;
  return toolInput && typeof toolInput === 'object' ? toolInput : {};
}

function getPatchText(input) {
  const toolInput = input.tool_input ?? input.toolInput;
  if (typeof toolInput === 'string') return toolInput;
  if (!toolInput || typeof toolInput !== 'object') return '';
  for (const key of ['patch', 'input', 'text', 'content', 'command']) {
    if (typeof toolInput[key] === 'string') return toolInput[key];
  }
  return '';
}

function parseTargets(input) {
  const patchText = getPatchText(input);
  const targets = [];
  let current = null;

  for (const line of patchText.split('\n')) {
    const match = line.match(/^\*\*\* (Add|Update|Delete) File: (.+)$/);
    if (match) {
      current = {
        action: match[1],
        filePath: match[2].trim(),
        snippet: `${line}\n`,
      };
      targets.push(current);
    } else if (current) {
      current.snippet += `${line}\n`;
    }
  }

  if (targets.length === 0) {
    const toolInput = getToolInput(input);
    const filePath = toolInput.file_path ?? toolInput.path;
    if (typeof filePath === 'string' && filePath) {
      const toolName = String(input.tool_name ?? input.toolName ?? '').toLowerCase();
      targets.push({
        action: toolName === 'write' ? 'Add' : 'Update',
        filePath,
        snippet: patchText,
      });
    }
  }
  return targets;
}

function resolveTarget(projectRoot, filePath) {
  const absolutePath = path.isAbsolute(filePath)
    ? path.resolve(filePath)
    : path.resolve(projectRoot, filePath);
  const root = path.resolve(projectRoot);
  if (absolutePath !== root && !absolutePath.startsWith(`${root}${path.sep}`)) {
    return null;
  }
  return absolutePath;
}

function synthesizePayload(input, target, absolutePath, content = '') {
  const isCreate = target.action === 'Add';
  const original = getToolInput(input);
  return {
    tool_name: isCreate ? 'Write' : 'Edit',
    tool_input: {
      ...original,
      file_path: absolutePath,
      content: isCreate ? content : (original.content ?? ''),
      old_string: original.old_string ?? '',
      new_string: original.new_string ?? (isCreate ? '' : target.snippet),
    },
  };
}

function normalizePath(value) {
  return value.split(path.sep).join('/');
}

function removeDeletedFile(projectRoot, absolutePath) {
  const wolfDir = path.join(projectRoot, '.wolf');
  const anatomyPath = path.join(wolfDir, 'anatomy.md');
  const relativePath = normalizePath(path.relative(projectRoot, absolutePath));
  const directory = normalizePath(path.dirname(relativePath));
  const sectionKey = directory === '.' ? './' : `${directory}/`;
  const fileName = path.basename(relativePath);

  try {
    const lines = fs.readFileSync(anatomyPath, 'utf-8').split('\n');
    let currentSection = '';
    const filtered = lines.filter((line) => {
      const heading = line.match(/^## (.+)$/);
      if (heading) currentSection = heading[1].trim();
      return !(
        currentSection === sectionKey &&
        line.startsWith(`- \`${fileName}\``)
      );
    });
    fs.writeFileSync(anatomyPath, filtered.join('\n'), 'utf-8');
  } catch {
    // OpenWolf maintenance must not block a successful edit.
  }

  try {
    const memoryPath = path.join(wolfDir, 'memory.md');
    const time = new Date().toTimeString().slice(0, 5);
    fs.appendFileSync(
      memoryPath,
      `| ${time} | Deleted ${relativePath} | removed file | ~0 |\n`,
      'utf-8',
    );
    const sessionPath = path.join(wolfDir, 'hooks', '_session.json');
    const session = JSON.parse(fs.readFileSync(sessionPath, 'utf-8'));
    session.files_written = session.files_written || [];
    session.edit_counts = session.edit_counts || {};
    session.files_written.push({
      file: relativePath,
      action: 'delete',
      tokens: 0,
      at: new Date().toISOString(),
    });
    session.edit_counts[relativePath] = (session.edit_counts[relativePath] || 0) + 1;
    fs.writeFileSync(sessionPath, JSON.stringify(session, null, 2), 'utf-8');
  } catch {
    // Keep hook behavior non-blocking.
  }
}

function sessionContext(projectRoot, hasWolf, hasCodeGraph) {
  const guidance = [];
  if (hasWolf) {
    guidance.push(
      'OpenWolf is active. Follow the repository AGENTS.md and consult .wolf/anatomy.md, .wolf/cerebrum.md, and .wolf/buglog.json at the appropriate points in the task.',
    );
  }
  if (hasCodeGraph) {
    guidance.push(
      `CodeGraph is active. For code discovery and impact analysis, use codegraph_explore with projectPath "${projectRoot}" before grep/find or broad file reads.`,
    );
  }
  return guidance.join(' ');
}

async function main() {
  const input = await readHookInput();
  const projectRoot = findProjectRoot(input);
  if (!projectRoot) return;

  const hasWolf = fs.existsSync(path.join(projectRoot, '.wolf'));
  const hasCodeGraph = fs.existsSync(path.join(projectRoot, '.codegraph'));
  if (!hasWolf && !hasCodeGraph) return;

  if (mode === 'session-start') {
    if (hasWolf) runOpenWolfHook(projectRoot, 'session-start.js', input);
    const additionalContext = sessionContext(projectRoot, hasWolf, hasCodeGraph);
    if (additionalContext) {
      process.stdout.write(JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'SessionStart',
          additionalContext,
        },
      }));
    }
    return;
  }

  if (!hasWolf) return;
  if (mode === 'stop') {
    runOpenWolfHook(projectRoot, 'stop.js', input);
    return;
  }

  for (const target of parseTargets(input)) {
    const absolutePath = resolveTarget(projectRoot, target.filePath);
    if (!absolutePath) continue;
    if (mode === 'pre-write') {
      runOpenWolfHook(
        projectRoot,
        'pre-write.js',
        synthesizePayload(input, target, absolutePath, target.snippet),
      );
    } else if (mode === 'post-write') {
      if (target.action === 'Delete') {
        removeDeletedFile(projectRoot, absolutePath);
        continue;
      }
      let content = '';
      try {
        content = fs.readFileSync(absolutePath, 'utf-8');
      } catch {
        // The native hook can still use the patch snippet.
      }
      runOpenWolfHook(
        projectRoot,
        'post-write.js',
        synthesizePayload(input, target, absolutePath, content),
      );
    }
  }
}

main().catch((error) => {
  process.stderr.write(`OpenWolf Codex adapter error: ${error.message}\n`);
  process.exit(0);
});
