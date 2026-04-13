/**
 * ModelUpdateBanner
 *
 * Checks for a new quantized model on mount (canary-gated by backend).
 * Shows a banner when an update is available, with a Download button.
 * Streams progress during download → verify → install.
 *
 * Usage: drop <ModelUpdateBanner domain="broker" /> in any page.
 */

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Download, CheckCircle2, AlertCircle, Loader2, X } from "lucide-react";

interface Artifact {
  quant_level: string;
  sha256: string;
  size_bytes: number;
}

interface UpdateInfo {
  version: string;
  minElectronVer: string;
  rollbackSafe: boolean;
  artifacts: Artifact[];
}

type Phase = "idle" | "checking" | "available" | "downloading" | "done" | "error";

interface DownloadProgress {
  phase: "downloading" | "verifying" | "installing";
  bytesReceived?: number;
  totalBytes?: number;
  percent?: number;
  detail?: string;
}

function formatBytes(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(0)} MB`;
  return `${bytes} B`;
}

// Pick the best quant: prefer q5_k_m, fall back to q4_k_m
function pickArtifact(artifacts: Artifact[]): Artifact {
  return (
    artifacts.find((a) => a.quant_level === "q5_k_m") ??
    artifacts.find((a) => a.quant_level === "q4_k_m") ??
    artifacts[0]
  );
}

export default function ModelUpdateBanner({ domain }: { domain: string }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [update, setUpdate] = useState<UpdateInfo | null>(null);
  const [progress, setProgress] = useState<DownloadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modelName, setModelName] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const listenerAttached = useRef(false);

  // Check for update on mount
  useEffect(() => {
    const modelApi = window.electron?.model;
    if (!modelApi) return;

    setPhase("checking");
    modelApi
      .checkUpdate(domain)
      .then((result) => {
        if (result.success && result.available && result.version && result.artifacts) {
          setUpdate({
            version: result.version,
            minElectronVer: result.minElectronVer ?? "",
            rollbackSafe: result.rollbackSafe ?? false,
            artifacts: result.artifacts,
          });
          setPhase("available");
        } else {
          setPhase("idle");
        }
      })
      .catch(() => setPhase("idle"));
  }, [domain]);

  const handleDownload = async () => {
    const modelApi = window.electron?.model;
    if (!update || !modelApi) return;

    const artifact = pickArtifact(update.artifacts);
    setPhase("downloading");
    setProgress(null);
    setError(null);

    if (!listenerAttached.current) {
      modelApi.onInstallProgress((p: DownloadProgress) => setProgress(p));
      listenerAttached.current = true;
    }

    try {
      const result = await modelApi.downloadAndInstall({
        domain,
        version: update.version,
        quant: artifact.quant_level,
        sha256Expected: artifact.sha256,
        sizeBytes: artifact.size_bytes,
      });

      if (result.success) {
        setModelName(result.modelName ?? null);
        setPhase("done");
      } else {
        setError(result.error ?? "Download failed");
        setPhase("error");
      }
    } catch (err: any) {
      setError(String(err?.message ?? err));
      setPhase("error");
    } finally {
      modelApi.removeInstallProgressListener();
      listenerAttached.current = false;
    }
  };

  // Nothing to show
  if (phase === "idle" || phase === "checking" || dismissed) return null;

  const artifact = update ? pickArtifact(update.artifacts) : null;

  return (
    <div className="rounded-xl border border-primary/30 bg-primary/5 backdrop-blur-sm p-4 mb-6 animate-in fade-in slide-in-from-top-2 duration-300">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1">
          {/* Icon */}
          <div className="mt-0.5 shrink-0">
            {phase === "done" ? (
              <CheckCircle2 className="h-5 w-5 text-green-500" />
            ) : phase === "error" ? (
              <AlertCircle className="h-5 w-5 text-destructive" />
            ) : phase === "downloading" ? (
              <Loader2 className="h-5 w-5 text-primary animate-spin" />
            ) : (
              <Download className="h-5 w-5 text-primary" />
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            {phase === "available" && update && artifact && (
              <>
                <p className="font-medium text-sm text-foreground">
                  Model update available — v{update.version}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {artifact.quant_level.toUpperCase()} · {formatBytes(artifact.size_bytes)}
                  {update.rollbackSafe && (
                    <Badge variant="outline" className="ml-2 text-[10px] py-0">rollback safe</Badge>
                  )}
                </p>
                <Button
                  size="sm"
                  className="mt-3"
                  onClick={handleDownload}
                >
                  <Download className="h-3.5 w-3.5 mr-1.5" />
                  Download & Install
                </Button>
              </>
            )}

            {phase === "downloading" && progress && (
              <>
                <p className="font-medium text-sm text-foreground capitalize">
                  {progress.phase === "downloading"
                    ? "Downloading model..."
                    : progress.phase === "verifying"
                    ? "Verifying integrity..."
                    : "Installing into Ollama..."}
                </p>
                {progress.detail && (
                  <p className="text-xs text-muted-foreground mt-0.5">{progress.detail}</p>
                )}
                {progress.phase === "downloading" && progress.totalBytes && (
                  <>
                    <Progress
                      value={progress.percent ?? 0}
                      className="mt-2 h-2"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      {formatBytes(progress.bytesReceived ?? 0)} / {formatBytes(progress.totalBytes)}
                      {" "}({progress.percent ?? 0}%)
                    </p>
                  </>
                )}
                {progress.phase !== "downloading" && (
                  <Progress value={100} className="mt-2 h-2 animate-pulse" />
                )}
              </>
            )}

            {phase === "done" && (
              <p className="font-medium text-sm text-green-600 dark:text-green-400">
                Model installed — <span className="font-mono text-xs">{modelName}</span> is ready in Ollama.
              </p>
            )}

            {phase === "error" && (
              <>
                <p className="font-medium text-sm text-destructive">Download failed</p>
                <p className="text-xs text-muted-foreground mt-0.5 break-all">{error}</p>
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-2"
                  onClick={() => { setPhase("available"); setError(null); }}
                >
                  Retry
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Dismiss — only when not actively downloading */}
        {phase !== "downloading" && (
          <button
            onClick={() => setDismissed(true)}
            className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Dismiss"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
