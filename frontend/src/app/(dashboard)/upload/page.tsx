"use client";

import { useState, useCallback, DragEvent } from "react";
import { UploadCloud, FileAudio, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function UploadPage() {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);

  const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  }, []);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Upload Meeting</h1>
        <p className="text-sm text-muted-foreground">
          Upload an audio or video recording to generate an AI meeting report.
        </p>
      </div>

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
                Supports MP3, WAV, MP4, MOV — up to 2GB
              </p>
              <label className="mt-4">
                <Input
                  type="file"
                  accept="audio/*,video/*"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])}
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
              <Button variant="ghost" size="icon" onClick={() => setFile(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">Meeting Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="title" className="text-sm font-medium">
              Meeting title
            </label>
            <Input id="title" placeholder="e.g. Q3 Product Launch Planning" />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Summary length</label>
            <div className="flex gap-2">
              <Button variant="outline" size="sm">
                Short
              </Button>
              <Button variant="outline" size="sm">
                Detailed
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end gap-3">
        <Button variant="outline">Cancel</Button>
        <Button disabled={!file}>Start Processing</Button>
      </div>
    </div>
  );
}
