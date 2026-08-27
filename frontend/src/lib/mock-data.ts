export type MeetingStatus = "processing" | "completed" | "failed";

export interface ActionItem {
  task: string;
  owner: string;
  deadline: string;
}

export interface Decision {
  text: string;
  timestamp: string;
}

export interface TranscriptLine {
  speaker: string;
  timestamp: string;
  text: string;
}

export interface Meeting {
  id: string;
  title: string;
  date: string;
  duration: string;
  status: MeetingStatus;
  participants: string[];
  summary: string;
  sentiment: "positive" | "neutral" | "mixed";
  keyPoints: string[];
  decisions: Decision[];
  actionItems: ActionItem[];
  unresolvedIssues: string[];
  transcript: TranscriptLine[];
}

export const mockMeetings: Meeting[] = [
  {
    id: "m1",
    title: "Q3 Product Launch Planning",
    date: "2026-08-18",
    duration: "42 min",
    status: "completed",
    participants: ["Ali Raza", "Sara Khan", "Bilal Ahmed"],
    summary:
      "Team aligned on the September 1 launch date, finalized homepage ownership, and flagged the marketing budget as still unresolved.",
    sentiment: "positive",
    keyPoints: [
      "Homepage redesign is the critical path item before launch",
      "Marketing budget needs sign-off from finance before next week",
      "QA pass planned for the week of Aug 25",
    ],
    decisions: [
      { text: "Product launch date is set for September 1.", timestamp: "12:04" },
      { text: "Homepage copy will use the v2 draft.", timestamp: "18:47" },
    ],
    actionItems: [
      { task: "Finish homepage build", owner: "Ali Raza", deadline: "Friday" },
      { task: "Get budget sign-off from finance", owner: "Sara Khan", deadline: "Next Monday" },
      { task: "Prepare QA test plan", owner: "Bilal Ahmed", deadline: "Aug 25" },
    ],
    unresolvedIssues: ["Marketing budget still pending finance approval"],
    transcript: [
      { speaker: "Sara Khan", timestamp: "00:12", text: "We should launch the website next week." },
      { speaker: "Ali Raza", timestamp: "00:34", text: "I'll complete the homepage by Friday." },
      { speaker: "Bilal Ahmed", timestamp: "12:04", text: "Let's lock the launch date as September 1." },
    ],
  },
  {
    id: "m2",
    title: "Weekly Engineering Standup",
    date: "2026-08-20",
    duration: "18 min",
    status: "processing",
    participants: ["Inza Iqbal", "Hamza Tariq"],
    summary: "",
    sentiment: "neutral",
    keyPoints: [],
    decisions: [],
    actionItems: [],
    unresolvedIssues: [],
    transcript: [],
  },
  {
    id: "m3",
    title: "Client Onboarding Call — Zenith Corp",
    date: "2026-08-15",
    duration: "55 min",
    status: "failed",
    participants: ["Inza Iqbal", "Client: Zenith Corp"],
    summary: "",
    sentiment: "neutral",
    keyPoints: [],
    decisions: [],
    actionItems: [],
    unresolvedIssues: [],
    transcript: [],
  },
];

export const dashboardMetrics = {
  totalMeetings: 24,
  pendingDecisions: 3,
  upcomingDeadlines: 5,
  actionItemsOpen: 9,
};
