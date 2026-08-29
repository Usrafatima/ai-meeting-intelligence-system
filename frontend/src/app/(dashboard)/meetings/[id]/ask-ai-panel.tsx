"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface ChatMessage {
  role: "user" | "ai";
  text: string;
  timestamp?: string;
}

export function AskAiPanel({ meetingTitle }: { meetingTitle: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "ai",
      text: `Ask me anything about "${meetingTitle}" — I'll answer using only this meeting's transcript.`,
    },
  ]);
  const [input, setInput] = useState("");

  function handleSend() {
    if (!input.trim()) return;
    const userMsg: ChatMessage = { role: "user", text: input };
    // Placeholder response — Module 7 (AI Q&A & RAG) wires this to the real backend.
    const aiMsg: ChatMessage = {
      role: "ai",
      text: "This is a placeholder response. Once the RAG backend is connected, this will answer grounded in the meeting transcript with a timestamp reference.",
      timestamp: "12:04",
    };
    setMessages((prev) => [...prev, userMsg, aiMsg]);
    setInput("");
  }

  return (
    <Card>
      <CardContent className="flex h-96 flex-col p-5">
        <div className="flex-1 space-y-4 overflow-y-auto pr-1">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
                  m.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                }`}
              >
                <p>{m.text}</p>
                {m.timestamp && (
                  <span className="mt-1 block text-xs opacity-70">Referenced at {m.timestamp}</span>
                )}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="What did we decide about the marketing budget?"
          />
          <Button onClick={handleSend} size="icon">
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
