import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { confirmDevicePairing, setStoredDeviceToken } from "@/lib/deviceApi";
import { supabase } from "@/integrations/supabase/client";
import { CheckCircle2, Link2, Loader2 } from "lucide-react";

function detectDeviceProfile() {
  return {
    device_name: `${navigator.platform || "Device"} ${new Date().toLocaleDateString()}`,
    os_name: navigator.platform || "unknown",
    app_version: "web-1.0.0",
    browser_name: navigator.userAgent,
    locale: navigator.language || "",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "",
    platform: navigator.platform || "",
    user_agent: navigator.userAgent,
    source: "device_link_qr",
    captured_at: new Date().toISOString(),
  };
}

export default function DeviceLinkConfirm() {
  const { toast } = useToast();
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [linked, setLinked] = useState(false);
  const [deviceToken, setDeviceToken] = useState("");
  const [deviceName, setDeviceName] = useState("");

  const pairingId = searchParams.get("pid") || "";
  const pairingCode = searchParams.get("code") || "";

  useEffect(() => {
    if (!deviceName) {
      setDeviceName(`${navigator.platform || "New Device"} ${new Date().toLocaleDateString()}`);
    }
  }, [deviceName]);

  const handleConfirm = async () => {
    if (!pairingId || !pairingCode) {
      toast({ title: "Invalid link", description: "Missing pairing values in URL.", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const profile = detectDeviceProfile();
      const result = await confirmDevicePairing({
        pairing_id: pairingId,
        pairing_code: pairingCode,
        auth_redirect_to: `${window.location.origin}/auth`,
        device_name: deviceName || profile.device_name,
        os_type: profile.os_name,
        app_version: profile.app_version,
        confirmed_device_profile: { ...profile, device_name: deviceName || profile.device_name },
      });
      setStoredDeviceToken(result.device.token);
      setDeviceToken(result.device.token);
      setLinked(true);
      toast({ title: "Device linked", description: "This device is now linked and ready to use." });
      if (result.login_action_link) {
        setTimeout(() => {
          window.location.href = result.login_action_link as string;
        }, 600);
      } else if (result.login_email && result.login_email_otp) {
        const { error } = await supabase.auth.verifyOtp({
          email: result.login_email,
          token: result.login_email_otp,
          type: "magiclink",
        });
        if (error) {
          throw new Error(`Device linked but auto-login failed: ${error.message}`);
        }
        window.location.href = "/";
      } else {
        toast({
          title: "Login handoff unavailable",
          description: result.login_handoff_error || "Device linked, but automatic sign-in link was not generated.",
          variant: "destructive",
        });
      }
    } catch (error: any) {
      toast({ title: "Link failed", description: error.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Link2 className="h-5 w-5 text-primary" />
            Confirm Device Link
          </CardTitle>
          <CardDescription>Complete linking for this device from the QR pairing session.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">Pairing ID</p>
            <Input value={pairingId} readOnly />
          </div>
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">Device Name</p>
            <Input value={deviceName} onChange={(e) => setDeviceName(e.target.value)} />
          </div>
          <Button onClick={handleConfirm} disabled={loading || linked} className="w-full">
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {linked ? "Linked" : "Link this device"}
          </Button>

          {linked && (
            <div className="rounded-md border border-green-500/30 bg-green-500/10 p-3 text-sm space-y-2">
              <p className="font-medium flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                Device linked successfully
              </p>
              <p className="text-xs break-all">Saved device token: {deviceToken}</p>
              <p className="text-xs text-muted-foreground">Token is also stored in browser localStorage as `device_token`.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
