import { useEffect, useMemo, useRef, useState } from "react";
import QRCode from "qrcode";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { getDevicePairingStatus, startDevicePairing } from "@/lib/deviceApi";
import { Link2, RefreshCw, Smartphone, CheckCircle2, Clock3 } from "lucide-react";

type PairingState = {
  pairingId: string;
  pairingCode: string;
  pairingUrl: string;
  expiresAt: string;
  status: "pending" | "confirmed" | "expired" | "cancelled";
};

export default function LinkDevices() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [pairing, setPairing] = useState<PairingState | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState("");
  const [linkedDeviceId, setLinkedDeviceId] = useState<string | null>(null);
  const pollingRef = useRef<number | null>(null);

  const expiresIn = useMemo(() => {
    if (!pairing) return 0;
    return Math.max(0, Math.floor((new Date(pairing.expiresAt).getTime() - Date.now()) / 1000));
  }, [pairing]);

  useEffect(() => {
    return () => {
      if (pollingRef.current) window.clearInterval(pollingRef.current);
    };
  }, []);

  const startPairing = async () => {
    setLoading(true);
    setLinkedDeviceId(null);
    try {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (!token) throw new Error("Please sign in again.");

      const response = await startDevicePairing(token, {
        frontend_base_url: window.location.origin,
        expires_in_seconds: 120,
        primary_device_label: `${navigator.platform || "web"}:${navigator.userAgent.slice(0, 60)}`,
        requested_device_profile: {
          source: "link_devices_page",
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "",
          locale: navigator.language || "",
          platform: navigator.platform || "",
        },
      });

      const qr = await QRCode.toDataURL(response.pairing_url, { width: 280, margin: 1 });
      setQrDataUrl(qr);
      setPairing({
        pairingId: response.pairing_id,
        pairingCode: response.pairing_code,
        pairingUrl: response.pairing_url,
        expiresAt: response.expires_at,
        status: response.status,
      });
      toast({ title: "QR ready", description: "Scan this code from the device you want to link." });

      if (pollingRef.current) window.clearInterval(pollingRef.current);
      pollingRef.current = window.setInterval(async () => {
        try {
          const status = await getDevicePairingStatus(token, response.pairing_id);
          setPairing((prev) =>
            prev
              ? {
                  ...prev,
                  status: status.pairing.status,
                  expiresAt: status.pairing.expires_at,
                }
              : prev
          );
          if (status.pairing.status === "confirmed" || status.pairing.status === "expired") {
            if (pollingRef.current) window.clearInterval(pollingRef.current);
          }
          if (status.pairing.status === "confirmed") {
            setLinkedDeviceId(status.pairing.linked_device_id || null);
            toast({ title: "Device linked", description: "A new device has been linked successfully." });
          }
        } catch (error: any) {
          if (pollingRef.current) window.clearInterval(pollingRef.current);
          toast({ title: "Pairing check failed", description: error.message, variant: "destructive" });
        }
      }, 3000);
    } catch (error: any) {
      toast({ title: "Could not start pairing", description: error.message, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Link Devices</h1>
        <p className="text-muted-foreground mt-1">Generate a QR code and scan it from another device to link instantly.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Link2 className="h-5 w-5" />
            Device Pairing QR
          </CardTitle>
          <CardDescription>QR expires in 2 minutes and can be used only once.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button onClick={startPairing} disabled={loading} className="gap-2">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            {loading ? "Creating QR..." : "Create New QR"}
          </Button>

          {pairing && (
            <div className="grid gap-4 md:grid-cols-[320px_1fr]">
              <div className="rounded-lg border p-4 flex items-center justify-center bg-white">
                {qrDataUrl ? (
                  <img src={qrDataUrl} alt="Device pairing QR" className="h-[280px] w-[280px]" />
                ) : (
                  <div className="h-[280px] w-[280px] flex items-center justify-center text-sm text-muted-foreground">
                    Generating QR...
                  </div>
                )}
              </div>
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Badge variant={pairing.status === "confirmed" ? "default" : "outline"}>
                    {pairing.status}
                  </Badge>
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Clock3 className="h-3 w-3" />
                    {expiresIn}s remaining
                  </span>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Pairing URL (manual fallback)</p>
                  <Input readOnly value={pairing.pairingUrl} />
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">One-time pairing code</p>
                  <Input readOnly value={pairing.pairingCode} />
                </div>
                {pairing.status === "confirmed" && (
                  <div className="rounded-md border border-green-500/30 bg-green-500/10 p-3 text-sm">
                    <p className="flex items-center gap-2 font-medium">
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      Device linked successfully
                    </p>
                    {linkedDeviceId && <p className="mt-1 text-xs text-muted-foreground">Device ID: {linkedDeviceId}</p>}
                  </div>
                )}
                {pairing.status === "expired" && (
                  <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm">
                    QR expired. Create a new one to continue linking.
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6 text-sm text-muted-foreground space-y-2">
          <p className="font-medium text-foreground flex items-center gap-2">
            <Smartphone className="h-4 w-4 text-primary" />
            How it works
          </p>
          <p>1) Open this page on your logged-in primary device.</p>
          <p>2) Scan the QR from the device you want to link.</p>
          <p>3) The new device is registered and can start check-ins immediately.</p>
        </CardContent>
      </Card>
    </div>
  );
}
