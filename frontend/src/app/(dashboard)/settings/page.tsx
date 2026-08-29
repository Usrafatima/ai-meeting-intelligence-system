import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export default function SettingsPage() {
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
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="name" className="text-sm font-medium">
              Full name
            </label>
            <Input id="name" defaultValue="Inza Iqbal" />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-sm font-medium">
              Email
            </label>
            <Input id="email" type="email" defaultValue="inzaiqbal54@gmail.com" />
          </div>
        </CardContent>
        <CardFooter className="justify-end">
          <Button>Save changes</Button>
        </CardFooter>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base text-foreground">Meeting Defaults</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Default summary length</label>
            <div className="flex gap-2">
              <Button variant="outline" size="sm">
                Short
              </Button>
              <Button variant="outline" size="sm">
                Detailed
              </Button>
            </div>
          </div>
          <div className="space-y-1.5">
            <label htmlFor="lang" className="text-sm font-medium">
              Transcription language
            </label>
            <Input id="lang" defaultValue="English" />
          </div>
        </CardContent>
        <CardFooter className="justify-end">
          <Button>Save preferences</Button>
        </CardFooter>
      </Card>
    </div>
  );
}
