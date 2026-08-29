import { Badge } from "@/components/ui/badge";

type MeetingStatus = "uploaded" | "queued" | "processing" | "transcribed" | "analyzed" | "completed" | "failed";

const statusMap: Record<MeetingStatus, { label: string; variant: "success" | "warning" | "destructive" | "muted" }> = {
  uploaded: { label: "Uploaded", variant: "muted" },
  queued: { label: "Queued", variant: "muted" },
  processing: { label: "Processing", variant: "warning" },
  transcribed: { label: "Transcribed", variant: "muted" },
  analyzed: { label: "Analyzed", variant: "muted" },
  completed: { label: "Completed", variant: "success" },
  failed: { label: "Failed", variant: "destructive" },
};

export function StatusBadge({ status }: { status: MeetingStatus }) {
  const { label, variant } = statusMap[status];
  return <Badge variant={variant}>{label}</Badge>;
}
