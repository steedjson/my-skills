export type RouteOverride = "L" | "S";

export type ControlCommand =
  | { kind: "none" }
  | { kind: "route"; route: RouteOverride }
  | { kind: "current" }
  | { kind: "auto"; enabled: boolean }
  | {
      kind: "approval";
      action: "approve" | "reject";
      taskId?: string;
      approvalToken?: string;
    }
  | { kind: "feedback"; label: "correct" | "incorrect"; taskId?: string }
  | { kind: "delete"; taskId?: string };

const COMMAND =
  /^\s*@(sol|luna|current|auto-off|auto-on|approve|reject|route-good|route-bad|delete)(?:\s+([A-Za-z0-9_-]{1,128}))?(?:\s+([A-Za-z0-9_-]{1,128}))?(?=\s|$)/i;

export function parseControlCommand(prompt: string): ControlCommand {
  const match = COMMAND.exec(prompt);
  if (!match) return { kind: "none" };

  const name = match[1]?.toLowerCase();
  const taskId = match[2];
  const approvalToken = match[3];
  switch (name) {
    case "sol":
      return { kind: "route", route: "S" };
    case "luna":
      return { kind: "route", route: "L" };
    case "current":
      return { kind: "current" };
    case "auto-off":
      return { kind: "auto", enabled: false };
    case "auto-on":
      return { kind: "auto", enabled: true };
    case "approve":
    case "reject":
      return taskId
        ? {
            kind: "approval",
            action: name,
            taskId,
            ...(approvalToken ? { approvalToken } : {}),
          }
        : { kind: "approval", action: name };
    case "route-good":
    case "route-bad": {
      const label = name === "route-good" ? "correct" : "incorrect";
      return taskId
        ? { kind: "feedback", label, taskId }
        : { kind: "feedback", label };
    }
    case "delete":
      return taskId ? { kind: "delete", taskId } : { kind: "delete" };
    default:
      return { kind: "none" };
  }
}

export function routeOverride(command: ControlCommand): RouteOverride | undefined {
  return command.kind === "route" ? command.route : undefined;
}
