"use client";

import { useEffect, useState } from "react";
import { notFound } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { getMeeting, getTranscript, Meeting } from "@/lib/api";
import { AskAiPanel } from "./ask-ai-panel";
import { Loader2 } from "lucide-react";

interface TranscriptSegment {
  start_time: number;
  end_time: number;
  speaker: string;
  text: string;
  confidence: number;
}

interface TranscriptData {
  meeting_id: string;
  raw_text: string;
  formatted_text: string;
  language: string;
  segments: TranscriptSegment[];
  overall_confidence?: number;
  duration_seconds?: number;
  transcriber_model: string;
}

export default function MeetingDetailsPage({ params }: { params: { id: string } }) {
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [transcript, setTranscript] = useState<TranscriptData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchData() {
      try {
        const meetingData = await getMeeting(params.id);
        setMeeting(meetingData);

        // Fetch transcript if meeting is processed
        if (meetingData.status === "transcribed" || meetingData.status === "analyzed" || meetingData.status === "completed") {
          try {
            const transcriptData = await getTranscript(params.id);
            setTranscript(transcriptData);
          } catch {
            // Transcript might not be available yet
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load meeting");
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [params.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !meeting) {
    return (
      <div className="py-10 text-center">
        <p className="text-destructive">{error || "Meeting not found"}</p>
      </div>
    );
  }

  const isProcessed = ["transcribed", "analyzed", "completed"].includes(meeting.status);
  const formatDuration = (seconds?: number) => {
    if (!seconds) return "N/A";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold">{meeting.title}</h1>
          <p className="text-sm text-muted-foreground">
            {meeting.meeting_date
              ? new Date(meeting.meeting_date).toLocaleDateString()
              : new Date(meeting.created_at).toLocaleDateString()}
            {" · "}
            {formatDuration(meeting.duration_seconds)}
            {meeting.participants?.length > 0 && (
              <>
                {" · "}
                {meeting.participants.map((p: any) => p.name || p.email || "Unknown").join(", ")}
              </>
            )}
          </p>
        </div>
        <StatusBadge status={meeting.status as any} />
      </div>

      {!isProcessed ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            {meeting.status === "processing"
              ? "This meeting is still being processed. Check back shortly for the full report."
              : meeting.status === "queued"
              ? "This meeting is queued for processing. It will be processed shortly."
              : meeting.status === "failed"
              ? "Processing failed for this meeting. Try re-uploading the recording."
              : "Waiting for processing to complete..."}
          </CardContent>
        </Card>
      ) : (
        <Tabs defaultValue="transcript">
          <TabsList>
            <TabsTrigger value="transcript">Transcript</TabsTrigger>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="ask">Ask AI</TabsTrigger>
          </TabsList>

          <TabsContent value="transcript">
            <Card>
              <CardHeader>
                <CardTitle className="text-base text-foreground">
                  Transcript
                  {transcript && (
                    <span className="ml-2 text-xs font-normal text-muted-foreground">
                      · {transcript.segments.length} segments · {transcript.language}
                    </span>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 p-5">
                {!transcript ? (
                  <p className="text-sm text-muted-foreground">Loading transcript...</p>
                ) : transcript.segments.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No transcript available.</p>
                ) : (
                  transcript.segments.map((line, i) => (
                    <div key={i} className="flex gap-3 text-sm">
                      <span className="w-14 shrink-0 font-mono text-xs text-muted-foreground">
                        {line.start_time.toFixed(1)}s
                      </span>
                      <div>
                        <span className="font-medium">{line.speaker}: </span>
                        <span>{line.text}</span>
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="overview">
            <Card>
              <CardHeader>
                <CardTitle className="text-base text-foreground">Raw Transcript</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-wrap text-sm">
                  {transcript?.raw_text || "Transcript not available yet."}
                </p>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="ask">
            <AskAiPanel meetingTitle={meeting.title} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
