"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/status-badge";
import { listMeetings } from "@/lib/api";
import { ListChecks, Clock, CalendarClock, Video, Plus, Loader2 } from "lucide-react";

interface MeetingSummary {
  id: string;
  title: string;
  status: string;
  duration_seconds?: number;
  meeting_date?: string;
  created_at: string;
  file_count: number;
}

export default function DashboardPage() {
  const [meetings, setMeetings] = useState<MeetingSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchMeetings() {
      try {
        const result = await listMeetings(1, 20);
        setMeetings(result.items);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load meetings");
      } finally {
        setLoading(false);
      }
    }

    fetchMeetings();
  }, []);

  const totalMeetings = meetings.length;
  const processingCount = meetings.filter((m) => m.status === "processing" || m.status === "queued").length;
  const completedCount = meetings.filter((m) => m.status === "completed" || m.status === "transcribed" || m.status === "analyzed").length;
  const failedCount = meetings.filter((m) => m.status === "failed").length;

  const metrics = [
    { label: "Total Meetings", value: totalMeetings, icon: Video },
    { label: "Processing", value: processingCount, icon: Clock },
    { label: "Completed", value: completedCount, icon: CalendarClock },
    { label: "Failed", value: failedCount, icon: ListChecks },
  ];

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
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : error ? (
            <div className="py-10 text-center text-sm text-destructive">
              {error}
            </div>
          ) : meetings.length === 0 ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              No meetings yet. Upload your first meeting to get started.
            </div>
          ) : (
            <div className="divide-y divide-border">
              {meetings.map((meeting) => (
                <Link
                  key={meeting.id}
                  href={`/meetings/${meeting.id}`}
                  className="flex items-center justify-between px-5 py-4 transition-colors hover:bg-muted/50"
                >
                  <div>
                    <p className="text-sm font-medium">{meeting.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {meeting.meeting_date
                        ? new Date(meeting.meeting_date).toLocaleDateString()
                        : new Date(meeting.created_at).toLocaleDateString()}
                      {meeting.duration_seconds && ` · ${Math.round(meeting.duration_seconds / 60)} min`}
                      {" · "}
                      {meeting.file_count} file{meeting.file_count !== 1 ? "s" : ""}
                    </p>
                  </div>
                  <StatusBadge status={meeting.status as any} />
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
