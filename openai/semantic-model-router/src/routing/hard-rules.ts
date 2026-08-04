export type RiskTag =
  | "destructive"
  | "external_side_effect"
  | "permission_or_security"
  | "schema_or_migration"
  | "credential_handling";

const RULES: ReadonlyArray<[RiskTag, RegExp]> = [
  [
    "destructive",
    /(?:\b(?:delete|remove|drop|truncate|overwrite|reset\s+--hard|rm\s+-rf)\b|删除|清空|覆盖|硬重置)/i,
  ],
  [
    "external_side_effect",
    /(?:\b(?:publish|deploy|push|send|email|message|charge|refund)\b|发布|部署|推送|发送|付款|扣款|退款)/i,
  ],
  [
    "permission_or_security",
    /(?:\b(?:permission|authorization|authentication|tenant|security|access control)\b|权限|鉴权|认证|租户|安全)/i,
  ],
  [
    "schema_or_migration",
    /(?:\b(?:schema|migration|migrate|database structure)\b|数据库结构|数据迁移|表结构)/i,
  ],
  [
    "credential_handling",
    /(?:\b(?:api[_ -]?key|secret|password|credential|token)\b|密钥|密码|凭证|令牌)/i,
  ],
];

export function detectRiskTags(prompt: string): RiskTag[] {
  return RULES.filter(([, pattern]) => pattern.test(prompt)).map(([tag]) => tag);
}
