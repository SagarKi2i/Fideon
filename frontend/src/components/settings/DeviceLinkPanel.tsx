import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { linkDeviceById } from "@/lib/deviceLinkApi";
import { Link2 } from "lucide-react";

export function DeviceLinkPanel() {
  const { toast } = useToast();
  const [deviceId, setDeviceId] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLink = async () => {
    const raw = deviceId.trim();
    if (!raw) {
      toast({ title: "Device ID required", variant: "destructive" });
      return;
    }
    try {
      setLoading(true);
      await linkDeviceById(raw);
      toast({ title: "Device linked", description: "This device is now connected to your tenant." });
      setDeviceId("");
    } catch (e) {
      toast({
        title: "Link failed",
        description: e instanceof Error ? e.message : "Unknown error",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="bg-card border-border shadow-card">
      <CardHeader>
        <CardTitle className="text-card-foreground flex items-center gap-2">
          <Link2 className="h-5 w-5 text-primary" />
          Link a device
        </CardTitle>
        <CardDescription>
          Paste the Device ID shown in the Electron app (Device Setup) to connect it to your account.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-2">
          <Label htmlFor="device-id">Device ID</Label>
          <Input
            id="device-id"
            placeholder="e.g. 7f6e3f3a-...."
            value={deviceId}
            onChange={(e) => setDeviceId(e.target.value)}
            className="font-mono text-xs"
          />
        </div>
        <Button onClick={() => void handleLink()} disabled={loading} className="bg-gradient-primary">
          {loading ? "Linking…" : "Link device"}
        </Button>
      </CardContent>
    </Card>
  );
}

