import { Badge } from "@/components/ui/badge";
import type { MeetingStatus } from "@/lib/mock-data";

const statusMap: Record<MeetingStatus, { label: string; variant: "success" | "warning" | "destructive" }> = {
  completed: { label: "Completed", variant: "success" },
  processing: { label: "Processing", variant: "warning" },
  failed: { label: "Failed", variant: "destructive" },
};

export function StatusBadge({ status }: { status: MeetingStatus }) {
  const { label, variant } = statusMap[status];
  return <Badge variant={variant}>{label}</Badge>;
}
