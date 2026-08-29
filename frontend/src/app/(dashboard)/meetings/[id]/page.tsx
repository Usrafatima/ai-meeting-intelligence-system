import { notFound } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { mockMeetings } from "@/lib/mock-data";
import { AskAiPanel } from "./ask-ai-panel";

export function generateStaticParams() {
  return mockMeetings.map((m) => ({ id: m.id }));
}

export default function MeetingDetailsPage({ params }: { params: { id: string } }) {
  const meeting = mockMeetings.find((m) => m.id === params.id);
  if (!meeting) return notFound();

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold">{meeting.title}</h1>
          <p className="text-sm text-muted-foreground">
            {meeting.date} · {meeting.duration} · {meeting.participants.join(", ")}
          </p>
        </div>
        <StatusBadge status={meeting.status} />
      </div>

      {meeting.status !== "completed" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            {meeting.status === "processing"
              ? "This meeting is still being processed. Check back shortly for the full report."
              : "Processing failed for this meeting. Try re-uploading the recording."}
          </CardContent>
        </Card>
      ) : (
        <Tabs defaultValue="overview">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="transcript">Transcript</TabsTrigger>
            <TabsTrigger value="insights">AI Insights</TabsTrigger>
            <TabsTrigger value="ask">Ask AI</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            <Card>
              <CardHeader>
                <CardTitle className="text-base text-foreground">Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm">{meeting.summary}</p>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Sentiment:</span>
                  <Badge variant="muted" className="capitalize">
                    {meeting.sentiment}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="transcript">
            <Card>
              <CardContent className="space-y-4 p-5">
                {meeting.transcript.map((line, i) => (
                  <div key={i} className="flex gap-3 text-sm">
                    <span className="w-14 shrink-0 font-mono text-xs text-muted-foreground">
                      {line.timestamp}
                    </span>
                    <div>
                      <span className="font-medium">{line.speaker}: </span>
                      <span>{line.text}</span>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="insights">
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base text-foreground">Key Points</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="list-disc space-y-2 pl-4 text-sm">
                    {meeting.keyPoints.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base text-foreground">Decisions</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {meeting.decisions.map((d, i) => (
                    <div key={i} className="text-sm">
                      <p>{d.text}</p>
                      <span className="font-mono text-xs text-muted-foreground">{d.timestamp}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base text-foreground">Action Items</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-xs text-muted-foreground">
                        <th className="px-5 py-2 font-medium">Task</th>
                        <th className="px-5 py-2 font-medium">Owner</th>
                        <th className="px-5 py-2 font-medium">Deadline</th>
                      </tr>
                    </thead>
                    <tbody>
                      {meeting.actionItems.map((a, i) => (
                        <tr key={i} className="border-b border-border last:border-0">
                          <td className="px-5 py-3">{a.task}</td>
                          <td className="px-5 py-3">{a.owner}</td>
                          <td className="px-5 py-3">{a.deadline}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base text-foreground">Unresolved Issues</CardTitle>
                </CardHeader>
                <CardContent>
                  {meeting.unresolvedIssues.length === 0 ? (
                    <p className="text-sm text-muted-foreground">None flagged.</p>
                  ) : (
                    <ul className="list-disc space-y-2 pl-4 text-sm">
                      {meeting.unresolvedIssues.map((u, i) => (
                        <li key={i}>{u}</li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="ask">
            <AskAiPanel meetingTitle={meeting.title} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
