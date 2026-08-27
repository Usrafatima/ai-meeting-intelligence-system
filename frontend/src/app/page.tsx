import Link from "next/link";
import {
  Sparkles,
  ArrowRight,
  Upload,
  Mic,
  CheckCircle2,
  FileText,
  Calendar,
  MessageSquare,
  Smile,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

const pipeline = [
  {
    step: "01",
    title: "Upload",
    description: "Drop in an audio or video file, or record the meeting directly in the browser.",
    icon: Upload,
  },
  {
    step: "02",
    title: "Transcribe",
    description: "Speech-to-text with speaker identification and timestamps preserved throughout.",
    icon: Mic,
  },
  {
    step: "03",
    title: "Analyze",
    description: "The model pulls out decisions, action items, deadlines, and open questions.",
    icon: Sparkles,
  },
  {
    step: "04",
    title: "Report",
    description: "A structured meeting report you can search, question, and act on.",
    icon: FileText,
  },
];

const features = [
  {
    title: "Speaker-aware transcripts",
    description: "Know who said what, down to the timestamp — not just a wall of text.",
    icon: Mic,
  },
  {
    title: "Action items, assigned",
    description: "Every commitment captured with an owner and a deadline, no digging through the recording.",
    icon: CheckCircle2,
  },
  {
    title: "Decision log",
    description: "Decisions are pulled out and saved the moment they're made, in plain language.",
    icon: FileText,
  },
  {
    title: "Deadline detection",
    description: "\u201CFriday\u201D and \u201Cend of the month\u201D become structured dates you can actually track.",
    icon: Calendar,
  },
  {
    title: "Ask AI",
    description: "Ask what was decided about the budget and get an answer with the exact timestamp.",
    icon: MessageSquare,
  },
  {
    title: "Meeting sentiment",
    description: "A read on how the room felt, alongside the facts.",
    icon: Smile,
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Nav */}
      <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <span className="text-base font-semibold">Meeting Intelligence</span>
          </div>
          <nav className="flex items-center gap-2">
            <Link href="/login">
              <Button variant="ghost" size="sm">
                Sign in
              </Button>
            </Link>
            <Link href="/signup">
              <Button size="sm">Get started</Button>
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="relative mx-auto max-w-6xl overflow-hidden px-6 pb-20 pt-16 md:pt-24">
        {/* Ambient glow */}
        <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
          <div className="motion-safe:animate-[float-slow_9s_ease-in-out_infinite] absolute -top-16 left-[10%] h-72 w-72 rounded-full bg-primary/15 blur-3xl" />
          <div className="motion-safe:animate-[float-slow_11s_ease-in-out_infinite] [animation-delay:1.2s] absolute top-40 right-[5%] h-64 w-64 rounded-full bg-primary/10 blur-3xl" />
        </div>

        <div className="grid items-center gap-14 md:grid-cols-2">
          <div>
            <Badge className="motion-safe:animate-[fade-up_0.6s_ease-out_both] mb-5 gap-1.5 py-1">
              <Sparkles className="h-3.5 w-3.5" />
              AI-powered meeting reports
            </Badge>
            <h1 className="motion-safe:animate-[fade-up_0.6s_ease-out_both] [animation-delay:80ms] text-4xl font-semibold leading-[1.1] tracking-tight text-foreground md:text-5xl">
              Your meetings, minus the manual notes.
            </h1>
            <p className="motion-safe:animate-[fade-up_0.6s_ease-out_both] [animation-delay:160ms] mt-5 max-w-md text-base leading-relaxed text-muted-foreground">
              Upload a recording and Meeting Intelligence turns the conversation into a
              structured report — decisions, action items, owners, and deadlines — ready
              to search and question.
            </p>
            <div className="motion-safe:animate-[fade-up_0.6s_ease-out_both] [animation-delay:240ms] mt-8 flex flex-wrap items-center gap-3">
              <Link href="/signup">
                <Button size="lg" className="gap-2 transition-transform hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98]">
                  Get started free
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="#how-it-works">
                <Button variant="outline" size="lg" className="transition-transform hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98]">
                  See how it works
                </Button>
              </Link>
            </div>
          </div>

          {/* Signature panel: unstructured -> structured */}
          <Card className="motion-safe:animate-[fade-left_0.7s_ease-out_both] [animation-delay:200ms] overflow-hidden transition-shadow hover:shadow-md">
            <div className="grid grid-cols-1 divide-y divide-border sm:grid-cols-2 sm:divide-x sm:divide-y-0">
              <div className="p-5">
                <div className="mb-4 flex items-center gap-2">
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-destructive/60" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-destructive" />
                  </span>
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Raw conversation
                  </span>
                </div>
                <div className="space-y-3 text-sm">
                  <p className="motion-safe:animate-[fade-up_0.5s_ease-out_both] [animation-delay:420ms]">
                    <span className="font-medium text-foreground">Speaker 2</span>
                    <span className="ml-2 text-xs text-muted-foreground">18:47</span>
                    <br />
                    <span className="text-muted-foreground">
                      &ldquo;I&rsquo;ll have the backend done by Friday.&rdquo;
                    </span>
                  </p>
                  <p className="motion-safe:animate-[fade-up_0.5s_ease-out_both] [animation-delay:520ms]">
                    <span className="font-medium text-foreground">Speaker 1</span>
                    <span className="ml-2 text-xs text-muted-foreground">19:02</span>
                    <br />
                    <span className="text-muted-foreground">
                      &ldquo;Okay — let&rsquo;s launch September 1st, then.&rdquo;
                    </span>
                  </p>
                </div>
              </div>
              <div className="bg-muted/40 p-5">
                <div className="mb-4 flex items-center gap-2">
                  <Sparkles className="h-3.5 w-3.5 text-primary" />
                  <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    AI insights
                  </span>
                </div>
                <div className="space-y-2.5">
                  <div className="motion-safe:animate-[fade-up_0.5s_ease-out_both] [animation-delay:640ms] rounded-md border border-border bg-background p-3 transition-transform hover:-translate-y-0.5">
                    <Badge variant="warning" className="mb-1.5">
                      Action item
                    </Badge>
                    <p className="text-sm text-foreground">Finish backend</p>
                    <p className="text-xs text-muted-foreground">Ali &middot; Due Friday</p>
                  </div>
                  <div className="motion-safe:animate-[fade-up_0.5s_ease-out_both] [animation-delay:760ms] rounded-md border border-border bg-background p-3 transition-transform hover:-translate-y-0.5">
                    <Badge variant="success" className="mb-1.5">
                      Decision
                    </Badge>
                    <p className="text-sm text-foreground">Launch date is September 1</p>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* Pipeline */}
      <section id="how-it-works" className="border-y border-border bg-muted/30">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-primary">
            How it works
          </h2>
          <p className="mt-2 max-w-lg text-2xl font-semibold tracking-tight text-foreground">
            From recording to report, automatically.
          </p>
          <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {pipeline.map(({ step, title, description, icon: Icon }) => (
              <div key={step} className="group">
                <div className="mb-3 flex items-center gap-2">
                  <span className="flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary transition-transform duration-300 group-hover:scale-110 group-hover:bg-primary/15">
                    <Icon className="h-4.5 w-4.5" />
                  </span>
                  <span className="text-xs font-medium text-muted-foreground">{step}</span>
                </div>
                <h3 className="text-sm font-semibold text-foreground">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                  {description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Feature grid */}
      <section className="mx-auto max-w-6xl px-6 py-16">
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">
          Everything the recording knows, made useful.
        </h2>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map(({ title, description, icon: Icon }) => (
            <Card
              key={title}
              className="group transition-all duration-200 hover:-translate-y-1 hover:border-primary/30 hover:shadow-md"
            >
              <CardContent className="p-5">
                <span className="mb-3 flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary transition-transform duration-300 group-hover:scale-110">
                  <Icon className="h-4.5 w-4.5" />
                </span>
                <h3 className="text-sm font-semibold text-foreground">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                  {description}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Product preview */}
      <section className="mx-auto max-w-6xl px-6 py-16">
        <Card className="overflow-hidden">
          <div className="border-b border-border p-5">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Meeting details
            </p>
            <h3 className="mt-1 text-base font-semibold text-foreground">
              Q3 Product Launch Planning
            </h3>
          </div>
          <CardContent className="p-5">
            <Tabs defaultValue="insights">
              <TabsList>
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="transcript">Transcript</TabsTrigger>
                <TabsTrigger value="insights">AI Insights</TabsTrigger>
                <TabsTrigger value="ask">Ask AI</TabsTrigger>
              </TabsList>
              <TabsContent value="overview">
                <p className="text-sm leading-relaxed text-muted-foreground">
                  Team aligned on the September 1 launch date, finalized homepage
                  ownership, and flagged the marketing budget as still unresolved.
                </p>
              </TabsContent>
              <TabsContent value="transcript">
                <p className="text-sm leading-relaxed text-muted-foreground">
                  <span className="font-medium text-foreground">Speaker 1</span>{" "}
                  <span className="text-xs">(12:04)</span> — We should launch the website
                  next week.
                </p>
              </TabsContent>
              <TabsContent value="insights">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-md border border-border p-3">
                    <Badge variant="success" className="mb-1.5">
                      Decision
                    </Badge>
                    <p className="text-sm text-foreground">
                      Product launch date is September 1.
                    </p>
                  </div>
                  <div className="rounded-md border border-border p-3">
                    <Badge variant="warning" className="mb-1.5">
                      Action item
                    </Badge>
                    <p className="text-sm text-foreground">Finish backend</p>
                    <p className="text-xs text-muted-foreground">Ali &middot; Due Friday</p>
                  </div>
                </div>
              </TabsContent>
              <TabsContent value="ask">
                <p className="text-sm leading-relaxed text-muted-foreground">
                  &ldquo;What did we decide about the marketing budget?&rdquo; &mdash; still
                  unresolved, flagged for finance sign-off.
                </p>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </section>

      {/* CTA band */}
      <section className="border-t border-border bg-primary/5">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-5 px-6 py-16 text-center">
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">
            Stop taking notes. Start acting on them.
          </h2>
          <Link href="/signup">
            <Button size="lg" className="gap-2">
              Get started free
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-8 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <span>Meeting Intelligence</span>
          </div>
          <span>&copy; 2026 Meeting Intelligence. All rights reserved.</span>
        </div>
      </footer>
    </div>
  );
}