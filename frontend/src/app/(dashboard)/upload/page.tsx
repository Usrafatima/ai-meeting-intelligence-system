"use client";

import { useState, useCallback, DragEvent, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { UploadCloud, FileAudio, X, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createMeeting, uploadFile, processSTT } from "@/lib/api";

type SummaryLength = "short" | "detailed";

export default function UploadPage() {
  const router = useRouter();
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [summaryLength, setSummaryLength] = useState<SummaryLength>("short");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [processingStatus, setProcessingStatus] = useState("");

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) {
      setFile(dropped);
      // Auto-fill title from filename if empty
      if (!title) {
        const nameWithoutExt = dropped.name.replace(/\.[^/.]+$/, "");
        setTitle(nameWithoutExt);
      }
    }
  }, [title]);

  async function handleStartProcessing(e: FormEvent) {
    e.preventDefault();
    setError("");

    if (!file) {
      setError("Please select a file first.");
      return;
    }

    if (!title.trim()) {
      setError("Please enter a meeting title.");
      return;
    }

    setLoading(true);
    setProcessingStatus("Creating meeting...");

    try {
      // Step 1: Create meeting
      const meeting = await createMeeting({
        title: title.trim(),
        description: `Meeting processed with ${summaryLength} summary`,
      });

      setProcessingStatus("Uploading file...");
      const meetingId = meeting.id;

      // Step 2: Upload file
      await uploadFile(meetingId, file);

      setProcessingStatus("Processing transcription...");

      // Step 3: Trigger STT processing
      await processSTT(meetingId);

      setProcessingStatus("Complete!");

      // Step 4: Navigate to meeting details
      setTimeout(() => {
        router.push(`/meetings/${meetingId}`);
      }, 1000);

    } catch (err) {
      setError(err instanceof Error ? err.message : "Processing failed. Please try again.");
      setLoading(false);
      setProcessingStatus("");
    }
  }

  function handleCancel() {
    setFile(null);
    setTitle("");
    setSummaryLength("short");
    setError("");
    setProcessingStatus("");
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Upload Meeting</h1>
        <p className="text-sm text-muted-foreground">
          Upload an audio or video recording to generate an AI meeting report.
        </p>
      </div>

      <form onSubmit={handleStartProcessing} className="space-y-6">
        {/* File Upload Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-foreground">Recording</CardTitle>
          </CardHeader>
          <CardContent>
            {!file ? (
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
                  isDragging ? "border-primary bg-primary/5" : "border-border"
                }`}
              >
                <UploadCloud className="mb-3 h-8 w-8 text-muted-foreground" />
                <p className="text-sm font-medium">Drag & drop your file here</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Supports MP3, WAV, MP4, MOV - up to 2GB
                </p>
                <label className="mt-4 cursor-pointer">
                  <Input
                    type="file"
                    accept="audio/*,video/*"
                    className="hidden"
                    onChange={(e) => {
                      const selectedFile = e.target.files?.[0];
                      if (selectedFile) {
                        setFile(selectedFile);
                        if (!title) {
                          const nameWithoutExt = selectedFile.name.replace(/\.[^/.]+$/, "");
                          setTitle(nameWithoutExt);
                        }
                      }
                    }}
                  />
                  <span className="inline-flex h-10 cursor-pointer items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90">
                    Browse files
                  </span>
                </label>
              </div>
            ) : (
              <div className="flex items-center justify-between rounded-lg border border-border p-4">
                <div className="flex items-center gap-3">
                  <FileAudio className="h-5 w-5 text-primary" />
                  <div>
                    <p className="text-sm font-medium">{file.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {(file.size / (1024 * 1024)).toFixed(1)} MB
                    </p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  type="button"
                  onClick={() => setFile(null)}
                  disabled={loading}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Meeting Details Card */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-foreground">Meeting Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="title" className="text-sm font-medium">
                Meeting title
              </label>
              <Input
                id="title"
                placeholder="e.g. Q3 Product Launch Planning"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={loading}
                required
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Summary length</label>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant={summaryLength === "short" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSummaryLength("short")}
                  disabled={loading}
                >
                  Short
                </Button>
                <Button
                  type="button"
                  variant={summaryLength === "detailed" ? "default" : "outline"}
                  size="sm"
                  onClick={() => setSummaryLength("detailed")}
                  disabled={loading}
                >
                  Detailed
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Error Message */}
        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}

        {/* Processing Status */}
        {processingStatus && (
          <div className="flex items-center gap-2 text-sm text-primary">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>{processingStatus}</span>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={handleCancel}
            disabled={loading}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={!file || !title.trim() || loading}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing...
              </>
            ) : (
              "Start Processing"
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
