import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/status-badge";
import { dashboardMetrics, mockMeetings } from "@/lib/mock-data";
import { ListChecks, Clock, CalendarClock, Video, Plus } from "lucide-react";

const metrics = [
  { label: "Total Meetings", value: dashboardMetrics.totalMeetings, icon: Video },
  { label: "Pending Decisions", value: dashboardMetrics.pendingDecisions, icon: Clock },
  { label: "Upcoming Deadlines", value: dashboardMetrics.upcomingDeadlines, icon: CalendarClock },
  { label: "Open Action Items", value: dashboardMetrics.actionItemsOpen, icon: ListChecks },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Overview of your recent meetings and pending items.
          </p>
        </div>
        <Link href="/upload">
          <Button>
            <Plus className="h-4 w-4" />
            Upload Meeting
          </Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map((m) => {
          const Icon = m.icon;
          return (
            <Card key={m.label}>
              <CardContent className="flex items-center justify-between p-5">
                <div>
                  <p className="text-sm text-muted-foreground">{m.label}</p>
                  <p className="mt-1 text-2xl font-semibold">{m.value}</p>
                </div>
                <div className="rounded-full bg-primary/10 p-2.5">
                  <Icon className="h-5 w-5 text-primary" />
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">Recent Meetings</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="divide-y divide-border">
            {mockMeetings.map((meeting) => (
              <Link
                key={meeting.id}
                href={`/meetings/${meeting.id}`}
                className="flex items-center justify-between px-5 py-4 transition-colors hover:bg-muted/50"
              >
                <div>
                  <p className="text-sm font-medium">{meeting.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {meeting.date} · {meeting.duration} · {meeting.participants.length} participants
                  </p>
                </div>
                <StatusBadge status={meeting.status} />
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
