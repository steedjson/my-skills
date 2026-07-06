export const meta = {
  name: 'effort-routed-task',
  description: '根据任务描述自动路由到合适的 agent effort 级别和模型，再派遣执行 agent。支持手动 override。',
  phases: [
    { title: 'Route', detail: '调用 route-effort skill 决定 effort 级别和模型' },
    { title: 'Execute', detail: '用路由结果派遣执行 agent' },
  ],
};

const DEFAULT_TASK = '跨模块变更：修改公共缓存层，评估对各服务模块的影响范围';
const VALID_EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max'];
const VALID_MODELS = ['haiku', 'sonnet', 'fable', 'opus'];

// effort → 默认模型映射
const EFFORT_MODEL_MAP = {
  low:    'haiku',   // claude-haiku-4-5：机械任务，速度优先
  medium: 'sonnet',  // claude-sonnet-5：日常任务，能力/成本平衡
  high:   'sonnet',  // claude-sonnet-5：多文件开发，sonnet 足够
  xhigh:  'fable',   // claude-fable-5：跨模块深度分析
  max:    'fable',   // claude-fable-5：安全审计/并发/正确性极限
};

const taskDesc = args?.task ?? DEFAULT_TASK;
const overrideEffort = args?.effort;
const overrideModel  = args?.model;

// ── Phase 1: 路由 ──────────────────────────────────────────────
phase('Route');

let effort = 'medium';

// effort 路由（手动 override 或自动判断）
if (overrideEffort && VALID_EFFORTS.includes(overrideEffort)) {
  effort = overrideEffort;
  log(`手动 override：effort=${effort}（跳过路由）`);
} else {
  if (overrideEffort) {
    log(`WARN: 无效的 override 值 "${overrideEffort}"，将使用自动路由`);
  }
  try {
    const routeResult = await agent(
      `按照 route-effort skill 的规则，评估以下任务应使用哪个 effort 级别。\n` +
      `只返回 effort=<level>，level 取值：low/medium/high/xhigh/max，不要其他内容。\n` +
      `---\n${taskDesc}\n---`,
      { effort: 'medium', label: `route: ${taskDesc.slice(0, 40)}` }
    );
    const match = (routeResult || '').match(/effort=(low|medium|high|xhigh|max)/);
    if (match) {
      effort = match[1];
    } else {
      log('WARN: route agent 返回格式异常，降级到 medium');
    }
  } catch (e) {
    log(`WARN: route agent 调用失败（${e?.message ?? e}），降级到 medium`);
  }
}

// 模型路由：先检查 override，再按 effort 自动映射
let model;
if (overrideModel && VALID_MODELS.includes(overrideModel)) {
  model = overrideModel;
  log(`手动 override：model=${model}（跳过模型映射）`);
} else {
  if (overrideModel) {
    log(`WARN: 无效的 model override "${overrideModel}"，将使用自动映射`);
  }
  model = EFFORT_MODEL_MAP[effort];
}

log(`路由结果：effort=${effort}，model=${model}`);

// ── Phase 2: 执行 ──────────────────────────────────────────────
phase('Execute');

try {
  await agent(taskDesc, {
    effort,
    model,
    label: `execute [${effort}/${model}]: ${taskDesc.slice(0, 40)}`,
  });
} catch (e) {
  log(`ERROR: execute agent 调用失败（${e?.message ?? e}）`);
  throw e;
}

log(`任务完成，使用 effort=${effort}，model=${model}`);
