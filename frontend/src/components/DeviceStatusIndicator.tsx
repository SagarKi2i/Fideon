import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Wifi, WifiOff } from "lucide-react";
import { getStoredDeviceJwt } from "@/lib/deviceApi";

type Status = "connected" | "disconnected" | "unknown";

export function DeviceStatusIndicator() {
  const [status, setStatus] = useState<Status>("unknown");
  const navigate = useNavigate();

  const refresh = () => {
    const jwt = getStoredDeviceJwt();
    if (!jwt) {
      setStatus("disconnected");
      return;
    }
    // If Electron exposes a live auth check use it; otherwise trust the stored JWT.
    if (typeof window !== "undefined" && window.electron?.device?.getAuth) {
      void window.electron.device.getAuth().then((res) => {
        setStatus(res?.success && res.device_jwt ? "connected" : "disconnected");
      }).catch(() => setStatus("disconnected"));
    } else {
      setStatus("connected");
    }
  };

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, 30_000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (status === "unknown") return null;

  const connected = status === "connected";
  const label = connected ? "Device connected" : "Device not registered";

  return (
    <button
      type="button"
      onClick={() => navigate("/device-setup")}
      aria-label={`${label} — go to Device Setup`}
      title={label}
      className="flex items-center gap-1.5 rounded px-2 py-1 text-xs font-medium transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {connected ? (
        <Wifi className="h-3.5 w-3.5 text-green-500" aria-hidden="true" />
      ) : (
        <WifiOff className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
      )}
      <span className="hidden sm:inline text-muted-foreground">
        {connected ? "Device" : "No device"}
      </span>
    </button>
  );
}
