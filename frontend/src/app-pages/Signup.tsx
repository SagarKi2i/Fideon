import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import type { Database } from "@/integrations/supabase/types";
import { useToast } from "@/hooks/use-toast";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, ChevronLeft, ChevronRight, Cpu, MonitorSmartphone, Shield, Sparkles, User } from "lucide-react";

type WizardStep = 0 | 1 | 2 | 3;
type AppRole = Database["public"]["Enums"]["app_role"];
type DeviceType = "desktop" | "laptop" | "mobile" | "tablet" | "other";
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const APP_ROLES: Array<{ label: string; value: AppRole }> = [
  { label: "Global Admin", value: "global_admin" },
  { label: "Admin", value: "admin" },
  { label: "User", value: "user" },
  { label: "Viewer", value: "viewer" },
  { label: "Guest", value: "guest" },
];

const PLANS = [
  {
    id: "starter",
    name: "Starter",
    description: "Perfect for POCs and small teams getting started.",
    features: ["Up to 5 users", "1 environment", "Shared Groq API key"],
  },
  {
    id: "growth",
    name: "Growth",
    description: "For teams moving workloads into production.",
    features: ["Up to 25 users", "2 environments", "Observability and alerts"],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    description: "For regulated, multi-tenant deployments at scale.",
    features: ["Unlimited users", "Multi-region", "Advanced governance"],
  },
] as const;

const ALL_MODELS = [
  {
    id: "quote-generation",
    name: "Quote Generation Agent",
    domain: "insurance",
    description: "End-to-end commercial lines quote assistance.",
  },
  {
    id: "policy-comparison",
    name: "Policy Comparison Engine",
    domain: "insurance",
    description: "Side-by-side policy comparison with gap detection.",
  },
  {
    id: "document-retrieval",
    name: "Document Retrieval",
    domain: "insurance",
    description: "Fetch renewals, endorsements, invoices from carriers.",
  },
  {
    id: "claims-fnol",
    name: "Claims and FNOL Intelligence",
    domain: "insurance",
    description: "Analyze FNOL documents and detect claim red flags.",
  },
  {
    id: "coverage-validation",
    name: "Coverage Validation and Eligibility",
    domain: "insurance",
    description: "Validate eligibility, business class, and binding authority.",
  },
] as const;

export default function Signup() {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [step, setStep] = useState<WizardStep>(0);
  const [loading, setLoading] = useState(false);
  const [completed, setCompleted] = useState(false);

  const [tenantName, setTenantName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [selectedRole, setSelectedRole] = useState<AppRole>("global_admin");

  const [selectedPlan, setSelectedPlan] = useState<(typeof PLANS)[number]["id"]>("starter");
  const [selectedModelId, setSelectedModelId] = useState<(typeof ALL_MODELS)[number]["id"]>("quote-generation");
  const [deviceName, setDeviceName] = useState("My First Edge Device");
  const [deviceType, setDeviceType] = useState<DeviceType>("desktop");
  const [osName, setOsName] = useState("");
  const [osVersion, setOsVersion] = useState("");
  const [browserName, setBrowserName] = useState("");
  const [browserVersion, setBrowserVersion] = useState("");
  const [appVersion, setAppVersion] = useState("web-1.0.0");
  const [locale, setLocale] = useState("");
  const [timezone, setTimezone] = useState("");
  const [platform, setPlatform] = useState("");
  const [hardwareFingerprint, setHardwareFingerprint] = useState("");
  const [showAllModels, setShowAllModels] = useState(false);
  const [step0Errors, setStep0Errors] = useState<{
    tenantName?: string;
    fullName?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
  }>({});

  useEffect(() => {
    const parseBrowser = (ua: string) => {
      const checks = [
        { key: "Edg/", name: "Edge" },
        { key: "OPR/", name: "Opera" },
        { key: "Chrome/", name: "Chrome" },
        { key: "Firefox/", name: "Firefox" },
        { key: "Safari/", name: "Safari" },
      ];
      for (const check of checks) {
        const idx = ua.indexOf(check.key);
        if (idx >= 0) {
          const version = ua.slice(idx + check.key.length).split(/[ ;)]/)[0];
          return { name: check.name, version: version || "" };
        }
      }
      return { name: "Unknown", version: "" };
    };

    const detectOs = (ua: string) => {
      if (ua.includes("Windows")) return "Windows";
      if (ua.includes("Mac OS X")) return "macOS";
      if (ua.includes("Android")) return "Android";
      if (ua.includes("iPhone") || ua.includes("iPad")) return "iOS";
      if (ua.includes("Linux")) return "Linux";
      return "Unknown";
    };

    const detectDeviceType = (ua: string): DeviceType => {
      if (/iPad|Tablet|PlayBook|Silk/i.test(ua)) return "tablet";
      if (/Mobi|Android|iPhone/i.test(ua)) return "mobile";
      if (/Macintosh|Windows NT|Linux x86_64|X11/i.test(ua)) return "desktop";
      return "other";
    };

    const toSha256 = async (value: string) => {
      if (!window.crypto?.subtle) return "";
      const bytes = new TextEncoder().encode(value);
      const hash = await window.crypto.subtle.digest("SHA-256", bytes);
      return Array.from(new Uint8Array(hash))
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
    };

    const ua = navigator.userAgent;
    const parsedBrowser = parseBrowser(ua);
    setBrowserName(parsedBrowser.name);
    setBrowserVersion(parsedBrowser.version);
    setOsName(detectOs(ua));
    setDeviceType(detectDeviceType(ua));
    setLocale(navigator.language || "");
    setPlatform(navigator.platform || "");
    setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || "");

    const fingerprintSeed = [
      navigator.userAgent,
      navigator.language,
      navigator.platform,
      String(navigator.hardwareConcurrency || ""),
      `${window.screen?.width || ""}x${window.screen?.height || ""}`,
      Intl.DateTimeFormat().resolvedOptions().timeZone || "",
    ].join("|");
    toSha256(fingerprintSeed).then(setHardwareFingerprint).catch(() => setHardwareFingerprint(""));
  }, []);

  const canGoNext = () => {
    if (step === 0) {
      return !!tenantName && !!fullName && !!email && !!password && !!confirmPassword;
    }
    if (step === 1) {
      return !!selectedPlan;
    }
    if (step === 2) {
      return !!selectedModelId;
    }
    if (step === 3) {
      return !!deviceName.trim();
    }
    return true;
  };

  const validateStep0 = () => {
    const nextErrors: typeof step0Errors = {};
    const normalizedEmail = email.trim().toLowerCase();

    if (!tenantName.trim()) nextErrors.tenantName = "Tenant / Company Name is required.";
    if (!fullName.trim()) nextErrors.fullName = "Your name is required.";
    if (!normalizedEmail) nextErrors.email = "Work email is required.";
    else if (!EMAIL_RE.test(normalizedEmail)) nextErrors.email = "Enter a valid work email address.";
    if (!password) nextErrors.password = "Password is required.";
    else if (password.length < 8) nextErrors.password = "Password must be at least 8 characters.";
    if (!confirmPassword) nextErrors.confirmPassword = "Please confirm your password.";
    else if (password !== confirmPassword) nextErrors.confirmPassword = "Passwords do not match.";

    setStep0Errors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const nextStep = () => {
    if (step === 0) {
      const valid = validateStep0();
      if (!valid) {
        toast({
          title: "Missing information",
          description: "Please correct the highlighted fields to continue.",
          variant: "destructive",
        });
        return;
      }
    } else if (!canGoNext()) {
      toast({
        title: "Missing information",
        description: "Please complete this step before continuing.",
        variant: "destructive",
      });
      return;
    }
    setStep0Errors({});
    setStep((s) => (s < 3 ? ((s + 1) as WizardStep) : s));
  };

  const prevStep = () => {
    if (step > 0) {
      setStep((s) => ((s - 1) as WizardStep));
      return;
    }
    navigate("/auth");
  };

  const handleComplete = async () => {
    if (!canGoNext()) return;
    const normalizedEmail = email.trim().toLowerCase();
    if (!EMAIL_RE.test(normalizedEmail)) {
      toast({
        title: "Invalid email",
        description: "Enter a valid work email address before continuing.",
        variant: "destructive",
      });
      return;
    }
    setLoading(true);
    try {
      const nowIso = new Date().toISOString();
      const { data, error } = await supabase.auth.signUp({
        email: normalizedEmail,
        password,
        options: {
          data: {
            tenant_name: tenantName.trim(),
            full_name: fullName.trim(),
            requested_role: selectedRole,
            plan: selectedPlan,
            default_model_id: selectedModelId,
            device_name: deviceName.trim(),
            signup_started_at: nowIso,
            signup_wizard_version: "v1",
            device_profile: {
              device_name: deviceName.trim(),
              device_type: deviceType,
              os_name: osName,
              os_version: osVersion,
              app_version: appVersion,
              browser_name: browserName,
              browser_version: browserVersion,
              locale,
              timezone,
              platform,
              user_agent: navigator.userAgent,
              hardware_fingerprint_sha256: hardwareFingerprint,
              captured_at: nowIso,
              source: "signup_wizard",
            },
          },
        },
      });

      if (error) throw error;

      if (data.user) {
        const { error: profileError } = await supabase
          .from("app_users")
          .update({ full_name: fullName })
          .eq("user_id", data.user.id);
        if (profileError) {
          console.warn("Unable to update app_users full_name:", profileError.message);
        }
      }

      setCompleted(true);
      toast({
        title: "Tenant created",
        description: "Account setup complete. Continue to sign in.",
      });
    } catch (error: any) {
      console.error("Onboarding error:", error);
      const rawMessage = String(error?.message || "").toLowerCase();
      const friendlyMessage = rawMessage.includes("already registered")
        ? "This email is already registered. Try signing in or using password reset."
        : rawMessage.includes("password")
        ? "Password does not meet security requirements. Use at least 8 characters."
        : error?.message ?? "Something went wrong while creating your tenant.";
      toast({
        title: "Onboarding failed",
        description: friendlyMessage,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const renderStepContent = () => {
    switch (step) {
      case 0:
        return (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-semibold flex items-center gap-2">
                <User className="h-5 w-5 text-primary" />
                Account and Tenant
              </h2>
              <p className="text-sm text-muted-foreground">
                Create your tenant and the first admin account.
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="tenant-name">Tenant / Company Name</Label>
                <Input
                  id="tenant-name"
                  value={tenantName}
                  onChange={(e) => {
                    setTenantName(e.target.value);
                    if (step0Errors.tenantName) {
                      setStep0Errors((prev) => ({ ...prev, tenantName: undefined }));
                    }
                  }}
                  placeholder="Acme Insurance Brokers"
                  aria-invalid={Boolean(step0Errors.tenantName)}
                  className={step0Errors.tenantName ? "border-destructive focus-visible:ring-destructive" : ""}
                />
                {step0Errors.tenantName && (
                  <p className="text-xs text-destructive">{step0Errors.tenantName}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="full-name">Your Name</Label>
                <Input
                  id="full-name"
                  value={fullName}
                  onChange={(e) => {
                    setFullName(e.target.value);
                    if (step0Errors.fullName) {
                      setStep0Errors((prev) => ({ ...prev, fullName: undefined }));
                    }
                  }}
                  placeholder="Jane Doe"
                  aria-invalid={Boolean(step0Errors.fullName)}
                  className={step0Errors.fullName ? "border-destructive focus-visible:ring-destructive" : ""}
                />
                {step0Errors.fullName && (
                  <p className="text-xs text-destructive">{step0Errors.fullName}</p>
                )}
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="email">Work Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (step0Errors.email) {
                      setStep0Errors((prev) => ({ ...prev, email: undefined }));
                    }
                  }}
                  placeholder="you@company.com"
                  aria-invalid={Boolean(step0Errors.email)}
                  className={step0Errors.email ? "border-destructive focus-visible:ring-destructive" : ""}
                />
                {step0Errors.email && (
                  <p className="text-xs text-destructive">{step0Errors.email}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <PasswordInput
                  id="password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (step0Errors.password || step0Errors.confirmPassword) {
                      setStep0Errors((prev) => ({
                        ...prev,
                        password: undefined,
                        confirmPassword: undefined,
                      }));
                    }
                  }}
                  placeholder="At least 8 characters"
                  aria-invalid={Boolean(step0Errors.password)}
                  className={step0Errors.password ? "border-destructive focus-visible:ring-destructive" : ""}
                />
                {step0Errors.password && (
                  <p className="text-xs text-destructive">{step0Errors.password}</p>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Confirm Password</Label>
              <PasswordInput
                id="confirm-password"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value);
                  if (step0Errors.confirmPassword) {
                    setStep0Errors((prev) => ({ ...prev, confirmPassword: undefined }));
                  }
                }}
                placeholder="Re-enter password"
                aria-invalid={Boolean(step0Errors.confirmPassword)}
                className={step0Errors.confirmPassword ? "border-destructive focus-visible:ring-destructive" : ""}
              />
              {step0Errors.confirmPassword && (
                <p className="text-xs text-destructive">{step0Errors.confirmPassword}</p>
              )}
            </div>
            <div className="space-y-3">
              <Label>Role in this tenant</Label>
              <div className="grid gap-2 md:grid-cols-3">
                {APP_ROLES.map((role) => (
                  <button
                    key={role.value}
                    type="button"
                    onClick={() => setSelectedRole(role.value)}
                    className={`rounded-lg border p-3 text-left text-sm transition ${
                      selectedRole === role.value
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/40"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{role.label}</span>
                      {selectedRole === role.value && (
                        <CheckCircle2 className="h-4 w-4 text-primary" />
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        );
      case 1:
        return (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-semibold flex items-center gap-2">
                <Shield className="h-5 w-5 text-primary" />
                Choose a Plan
              </h2>
              <p className="text-sm text-muted-foreground">
                You can change plans later as you scale.
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              {PLANS.map((plan) => (
                <button
                  key={plan.id}
                  type="button"
                  onClick={() => setSelectedPlan(plan.id)}
                  className={`rounded-xl border p-4 text-left transition h-full ${
                    selectedPlan === plan.id
                      ? "border-primary bg-primary/5 shadow-sm"
                      : "border-border hover:border-primary/40"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold">{plan.name}</h3>
                    {selectedPlan === plan.id && (
                      <Badge className="text-[10px]">Selected</Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mb-3">
                    {plan.description}
                  </p>
                  <ul className="space-y-1 text-xs text-muted-foreground">
                    {plan.features.map((f) => (
                      <li key={f} className="flex items-center gap-1.5">
                        <CheckCircle2 className="h-3 w-3 text-primary" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                </button>
              ))}
            </div>
          </div>
        );
      case 2:
        return (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-semibold flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                Pick Your First Model
              </h2>
              <p className="text-sm text-muted-foreground">
                We keep this choice in onboarding metadata for initial setup.
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              {(showAllModels ? ALL_MODELS : ALL_MODELS.slice(0, 3)).map((model) => (
                <button
                  key={model.id}
                  type="button"
                  onClick={() => setSelectedModelId(model.id)}
                  className={`rounded-xl border p-4 text-left transition h-full ${
                    selectedModelId === model.id
                      ? "border-primary bg-primary/5 shadow-sm"
                      : "border-border hover:border-primary/40"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-sm">{model.name}</h3>
                    <Badge variant="outline" className="text-[10px] capitalize">
                      {model.domain}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {model.description}
                  </p>
                </button>
              ))}
            </div>
            {!showAllModels && ALL_MODELS.length > 3 && (
              <div className="flex justify-center">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowAllModels(true)}
                >
                  Show More Models
                </Button>
              </div>
            )}
          </div>
        );
      case 3:
        return (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-semibold flex items-center gap-2">
                <Cpu className="h-5 w-5 text-primary" />
                Link Your First Device
              </h2>
              <p className="text-sm text-muted-foreground">
                Enter a device name to store in onboarding metadata. You can complete linking from the app after login.
              </p>
            </div>
            <div className="space-y-3">
              <Label htmlFor="device-name">Device Name</Label>
              <Input
                id="device-name"
                value={deviceName}
                onChange={(e) => setDeviceName(e.target.value)}
                placeholder="Claims Desktop - Chicago Office"
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="device-type">Device Type</Label>
                <select
                  id="device-type"
                  value={deviceType}
                  onChange={(e) => setDeviceType(e.target.value as DeviceType)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="desktop">Desktop</option>
                  <option value="laptop">Laptop</option>
                  <option value="mobile">Mobile</option>
                  <option value="tablet">Tablet</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="app-version">App Version</Label>
                <Input
                  id="app-version"
                  value={appVersion}
                  onChange={(e) => setAppVersion(e.target.value)}
                  placeholder="web-1.0.0"
                />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="os-name">OS Name</Label>
                <Input
                  id="os-name"
                  value={osName}
                  onChange={(e) => setOsName(e.target.value)}
                  placeholder="Windows / macOS / Linux"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="os-version">OS Version</Label>
                <Input
                  id="os-version"
                  value={osVersion}
                  onChange={(e) => setOsVersion(e.target.value)}
                  placeholder="Optional"
                />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="browser-name">Browser Name</Label>
                <Input
                  id="browser-name"
                  value={browserName}
                  onChange={(e) => setBrowserName(e.target.value)}
                  placeholder="Chrome / Edge / Safari"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="browser-version">Browser Version</Label>
                <Input
                  id="browser-version"
                  value={browserVersion}
                  onChange={(e) => setBrowserVersion(e.target.value)}
                  placeholder="Optional"
                />
              </div>
            </div>
            <div className="rounded-lg border bg-muted/30 p-3 text-xs text-muted-foreground space-y-1">
              <p>Locale: {locale || "unknown"} | Timezone: {timezone || "unknown"}</p>
              <p>Platform: {platform || "unknown"}</p>
              <p>Fingerprint (sha256): {hardwareFingerprint ? `${hardwareFingerprint.slice(0, 20)}...` : "pending"}</p>
            </div>
            <div className="rounded-lg border bg-muted/40 p-4 text-xs text-muted-foreground flex gap-3">
              <MonitorSmartphone className="h-4 w-4 text-primary mt-0.5" />
              <div>
                <p className="font-medium text-foreground mb-1">What happens on complete setup</p>
                <ol className="list-decimal list-inside space-y-1">
                  <li>We create your user in Supabase Auth.</li>
                  <li>We store role, tenant name, plan, model, and device metadata.</li>
                  <li>Your role is assigned via your existing Supabase signup trigger.</li>
                </ol>
              </div>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background via-background to-background/95 p-4">
      <Card className="w-full max-w-4xl border-border/60 bg-card/90 backdrop-blur-xl shadow-2xl">
        <CardHeader className="space-y-3 border-b border-border/60">
          <div className="flex items-center justify-between gap-3">
            <div>
              <CardTitle className="text-xl md:text-2xl flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                Tenant Onboarding Wizard
              </CardTitle>
              <CardDescription className="text-xs md:text-sm">
                Sign-up to first model and device, in four guided steps.
              </CardDescription>
            </div>
            <Badge variant="outline" className="hidden md:inline-flex text-[11px]">
              4-step onboarding
            </Badge>
          </div>
          <div className="flex items-center gap-2 mt-2">
            {[0, 1, 2, 3].map((i) => {
              const active = step === i;
              const isCompleted = step > i || completed;
              return (
                <div key={i} className="flex-1 flex items-center gap-2">
                  <div
                    className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium border ${
                      isCompleted
                        ? "bg-primary text-primary-foreground border-primary"
                        : active
                        ? "bg-primary/10 text-primary border-primary/60"
                        : "bg-background text-muted-foreground border-border"
                    }`}
                  >
                    {isCompleted ? <CheckCircle2 className="h-4 w-4" /> : i + 1}
                  </div>
                  <div className="hidden md:block text-[11px] text-muted-foreground">
                    {i === 0 && "Account"}
                    {i === 1 && "Plan"}
                    {i === 2 && "Model"}
                    {i === 3 && "Device"}
                  </div>
                  {i < 3 && (
                    <div className="flex-1 h-[1px] bg-border/60" />
                  )}
                </div>
              );
            })}
          </div>
        </CardHeader>
        <CardContent className="p-4 md:p-6 space-y-6">
          {renderStepContent()}
          <div className="flex items-center justify-between pt-2 border-t border-border/60 mt-4">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={prevStep}
              disabled={loading || completed}
              className="flex items-center gap-1 text-xs md:text-sm"
            >
              <ChevronLeft className="h-3 w-3" />
              Back
            </Button>
            <div className="flex items-center gap-2">
              {step < 3 ? (
                <Button
                  type="button"
                  onClick={nextStep}
                  disabled={loading || completed}
                  className="flex items-center gap-1 text-xs md:text-sm"
                >
                  Next
                  <ChevronRight className="h-3 w-3" />
                </Button>
              ) : (
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    onClick={handleComplete}
                    disabled={!canGoNext() || loading || completed}
                    className="flex items-center gap-1 text-xs md:text-sm"
                  >
                    {loading ? "Creating..." : "Complete Setup"}
                  </Button>
                  {completed && (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => navigate("/auth")}
                      className="flex items-center gap-1 text-xs md:text-sm"
                    >
                      Go to Login
                    </Button>
                  )}
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
