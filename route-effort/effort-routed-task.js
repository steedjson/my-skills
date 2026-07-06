export const meta = {
  name: 'effort-routed-task',
  description: '演示如何通过 route-effort skill 自动决定 effort，再派遣子 agent 执行任务',
  phases: [
    { title: 'Route', detail: '调用 route-effort skill 决定 effort 级别' },
    { title: 'Execute', detail: '用路由结果派遣执行 agent' },
  ],
};

/**
 * 调用 route-effort skill 获取推荐的 effort 级别。
 * 路由本身用 low effort —— 无需推理，节省 token。
 */
async function routeEffort(taskDesc) {
  phase('Route');
  const result = await agent(
    `按照 route-effort skill 的规则，评估以下任务应使用哪个 effort 级别。\n` +
    `只返回 effort=<level>，level 取值：low/medium/high/xhigh/max，不要其他内容。\n\n` +
    `任务：${taskDesc}`,
    { effort: 'medium', label: `route: ${taskDesc.slice(0, 40)}` }  // medium：low 会系统性低估复杂任务
  );
  const match = (result || '').match(/effort=(low|medium|high|xhigh|max)/);
  return match ? match[1] : 'medium';
}

// ── 主流程 ────────────────────────────────────────────────────
// args 示例：{ task: "跨模块变更：修改认证中间件，评估影响范围" }
// 未传 args 时使用默认示例任务
const taskDesc = (args && args.task) ? args.task : '跨模块变更：修改公共缓存层，评估对各服务模块的影响范围';

const effort = await routeEffort(taskDesc);
log(`路由结果：effort=${effort}`);

phase('Execute');
const result = await agent(taskDesc, {
  effort,
  label: `execute [${effort}]: ${taskDesc.slice(0, 40)}`,
});

log(`任务完成，使用 effort=${effort}`);
