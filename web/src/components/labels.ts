export function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    queued: "排队中",
    running: "运行中",
    done: "已完成",
    failed: "失败",
    blocked: "已阻塞"
  };
  return labels[status] ?? status;
}
