export const meta = {
  name: 'effort-routed-task',
  description: '根据任务描述自动路由到合适的 agent effort 级别，再派遣执行 agent。支持手动 override。',
  phases: [
    { title: 'Route', detail: '调用 route-effort skill 决定 effort 级别' },
    { title: 'Execute', detail: '用路由结果派遣执行 agent' },
  ],
};

const DEFAULT_TASK = '跨模块变更：修改公共缓存层，评估对各服务模块的影响范围';
const VALID_EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max'];

// args?.task ?? DEFAULT_TASK：空字符串视为有效输入（非 falsy 替换）
const taskDesc = args?.task ?? DEFAULT_TASK;
const overrideEffort = args?.effort;

// ── Phase 1: 路由 ──────────────────────────────────────────────
phase('Route');

let effort = 'medium';

// 手动 override：传入有效的 effort 字段时跳过路由，零额外开销
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

log(`路由结果：effort=${effort}`);

// ── Phase 2: 执行 ──────────────────────────────────────────────
phase('Execute');

try {
  await agent(taskDesc, {
    effort,
    label: `execute [${effort}]: ${taskDesc.slice(0, 40)}`,
  });
} catch (e) {
  log(`ERROR: execute agent 调用失败（${e?.message ?? e}）`);
  throw e;
}

log(`任务完成，使用 effort=${effort}`);
