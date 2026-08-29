"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { getCurrentUser } from "@/lib/api";
import { Loader2 } from "lucide-react";

export default function SettingsPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    async function fetchUser() {
      try {
        const user = await getCurrentUser();
        setName(user.full_name || "");
        setEmail(user.email || "");
      } catch (err) {
        console.error("Failed to load user:", err);
      } finally {
        setLoading(false);
      }
    }

    fetchUser();
  }, []);

  async function handleSaveProfile(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMessage("");

    try {
      // TODO: Implement profile update API call
      await new Promise((resolve) => setTimeout(resolve, 500)); // Placeholder
      setMessage("Profile saved successfully!");
    } catch (err) {
      setMessage("Failed to save profile.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl space-y-6">
        <div>
          <h1 className="text-xl font-semibold">Settings</h1>
          <p className="text-sm text-muted-foreground">
            Manage your account and meeting processing preferences.
          </p>
        </div>
        <div className="flex items-center justify-center py-10">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your account and meeting processing preferences.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">Profile</CardTitle>
        </CardHeader>
        <form onSubmit={handleSaveProfile}>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="name" className="text-sm font-medium">
                Full name
              </label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={saving}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="email" className="text-sm font-medium">
                Email
              </label>
              <Input
                id="email"
                type="email"
                value={email}
                disabled
                className="bg-muted"
              />
              <p className="text-xs text-muted-foreground">
                Email cannot be changed.
              </p>
            </div>
            {message && (
              <p className={`text-sm ${message.includes("success") ? "text-green-600" : "text-destructive"}`}>
                {message}
              </p>
            )}
          </CardContent>
          <CardFooter className="justify-end">
            <Button type="submit" disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save changes"
              )}
            </Button>
          </CardFooter>
        </form>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">Meeting Defaults</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Default summary length</label>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" disabled>
                Short
              </Button>
              <Button variant="outline" size="sm" disabled>
                Detailed
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              This feature is coming soon.
            </p>
          </div>
          <div className="space-y-1.5">
            <label htmlFor="lang" className="text-sm font-medium">
              Transcription language
            </label>
            <Input id="lang" defaultValue="English" disabled />
            <p className="text-xs text-muted-foreground">
              This feature is coming soon.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
