import React, { useEffect, useRef, useState } from "react";
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
import { apiUrl } from "@/lib/apiBaseUrl";

type WizardStep = 0 | 1 | 2 | 3;
type AppRole = Database["public"]["Enums"]["app_role"];
type DeviceType = "desktop" | "laptop" | "mobile" | "tablet" | "other";
type NavigatorWithUserAgentData = Navigator & { userAgentData?: { platform?: string } };
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PASSWORD_STRENGTH_RE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).+$/;
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL as string | undefined;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY as string | undefined;
const LIMITS = {
  tenantName: { min: 2, max: 100 },
  fullName: { min: 2, max: 80 },
  email: { min: 6, max: 254, localPartMax: 64 },
  password: { min: 8, max: 72 },
};

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
    price: "$60,000 / year",
    description: "For independent agencies beginning their AI automation journey.",
    features: [
      "Up to 5 users",
      "1 agent pack",
      "Only 3 active AI models",
      "3 workflow slots included",
      "Community support",
    ],
    includedSlots: 3,
    maxAddonSlots: 5,
    maxPacks: 1,
    maxModels: 3,
  },
  {
    id: "professional",
    name: "Professional",
    price: "$180,000 / year",
    description: "For mid-size brokerages scaling AI across production workflows.",
    features: [
      "Up to 25 users",
      "3 agent packs",
      "Only 8 active AI models",
      "15 workflow slots included",
      "Agent pipeline scheduling",
      "Priority support",
    ],
    includedSlots: 15,
    maxAddonSlots: 5,
    maxPacks: 3,
    maxModels: 8,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "$480,000 / year",
    description: "For large brokerage groups and regulated carriers — unlimited scale and unlimited models.",
    features: [
      "Unlimited users",
      "Unlimited agent packs",
      "Unlimited active AI models",
      "Unlimited scale",
      "Unlimited workflow slots",
      "Full agent pipeline suite",
      "Dedicated SLA support (24/7)",
    ],
    includedSlots: null,
    maxAddonSlots: 0,
    maxPacks: null,
    maxModels: null,
  },
] as const;

const STEP_META = [
  { index: 0, label: "Account" },
  { index: 1, label: "Plan" },
  { index: 2, label: "Agent Packs" },
  { index: 3, label: "Device" },
] as const;

const AGENT_PACKS = [
  {
    id: "underwriting",
    name: "Underwriting Pack",
    description: "Quote generation, coverage validation, ACORD parsing, submission intake.",
  },
  {
    id: "claims",
    name: "Claims Pack",
    description: "FNOL intelligence, claims adjudication, fraud flag review.",
  },
  {
    id: "distribution",
    name: "Distribution Pack",
    description: "Policy comparison, document retrieval, renewal packets.",
  },
  {
    id: "compliance",
    name: "Compliance Pack",
    description: "Compliance checks, COI issuance, regulatory validation.",
  },
  {
    id: "agentic-rag",
    name: "Agentic RAG Add-On",
    description: "Retrieval-augmented generation over carrier and policy docs.",
  },
] as const;

type TenantSignupConfig = {
  tenant: { id: string; slug: string; name: string };
  plan: (typeof PLANS)[number]["id"] | string;
  agent_packs: string[];
  max_agent_packs: number | null;
  remaining_pack_slots: number | null;
  workflow_addon_slots: number;
  workflow_slots_total: number | null;
};

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
  const [workflowAddonSlots, setWorkflowAddonSlots] = useState(0);
  const [selectedPacks, setSelectedPacks] = useState<string[]>([]);
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
  const [step0Errors, setStep0Errors] = useState<{
    tenantName?: string;
    fullName?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
  }>({});
  const [checkingEmail, setCheckingEmail] = useState(false);
  const [emailCheckError, setEmailCheckError] = useState<string | null>(null);
  const [lastCheckedEmail, setLastCheckedEmail] = useState("");
  const [lastCheckedEmailExists, setLastCheckedEmailExists] = useState<boolean | null>(null);
  const emailAvailabilityCacheRef = useRef<Map<string, boolean>>(new Map());
  const emailCheckControllerRef = useRef<AbortController | null>(null);

  const [tenantConfig, setTenantConfig] = useState<TenantSignupConfig | null>(null);
  const [checkingTenant, setCheckingTenant] = useState(false);
  const [tenantCheckError, setTenantCheckError] = useState<string | null>(null);
  const tenantCheckControllerRef = useRef<AbortController | null>(null);

  const buildStep0Errors = () => {
    const nextErrors: typeof step0Errors = {};
    const normalizedEmail = email.trim().toLowerCase();
    const emailLocalPart = normalizedEmail.split("@")[0] || "";

    if (!tenantName.trim()) nextErrors.tenantName = "Tenant / Company Name is required.";
    else if (tenantName.trim().length < LIMITS.tenantName.min) {
      nextErrors.tenantName = `Tenant / Company Name must be at least ${LIMITS.tenantName.min} characters.`;
    } else if (tenantName.trim().length > LIMITS.tenantName.max) {
      nextErrors.tenantName = `Tenant / Company Name must be ${LIMITS.tenantName.max} characters or fewer.`;
    }
    if (!fullName.trim()) nextErrors.fullName = "Your name is required.";
    else if (fullName.trim().length < LIMITS.fullName.min) {
      nextErrors.fullName = `Your name must be at least ${LIMITS.fullName.min} characters.`;
    } else if (fullName.trim().length > LIMITS.fullName.max) {
      nextErrors.fullName = `Your name must be ${LIMITS.fullName.max} characters or fewer.`;
    }
    if (!normalizedEmail) nextErrors.email = "Work email is required.";
    else if (normalizedEmail.length < LIMITS.email.min || normalizedEmail.length > LIMITS.email.max) {
      nextErrors.email = `Work email must be ${LIMITS.email.min}-${LIMITS.email.max} characters.`;
    } else if (emailLocalPart.length > LIMITS.email.localPartMax) {
      nextErrors.email = `Email username must be ${LIMITS.email.localPartMax} characters or fewer.`;
    }
    else if (!EMAIL_RE.test(normalizedEmail)) nextErrors.email = "Enter a valid work email address.";
    if (!password) nextErrors.password = "Password is required.";
    else if (password.length < LIMITS.password.min || password.length > LIMITS.password.max) {
      nextErrors.password = `Password must be ${LIMITS.password.min}-${LIMITS.password.max} characters.`;
    } else if (!PASSWORD_STRENGTH_RE.test(password)) {
      nextErrors.password = "Use at least 1 uppercase, 1 lowercase, 1 number, and 1 special character.";
    }
    if (!confirmPassword) nextErrors.confirmPassword = "Please confirm your password.";
    else if (password !== confirmPassword) nextErrors.confirmPassword = "Passwords do not match.";

    return nextErrors;
  };

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
    const detectPlatform = (ua: string) => {
      const platformFromUaData = (navigator as NavigatorWithUserAgentData).userAgentData?.platform;
      if (platformFromUaData) return platformFromUaData;
      return detectOs(ua);
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
    const resolvedPlatform = detectPlatform(ua);
    setPlatform(resolvedPlatform || "");
    setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone || "");

    const fingerprintSeed = [
      navigator.userAgent,
      navigator.language,
      resolvedPlatform,
      String(navigator.hardwareConcurrency || ""),
      `${window.screen?.width || ""}x${window.screen?.height || ""}`,
      Intl.DateTimeFormat().resolvedOptions().timeZone || "",
    ].join("|");
    toSha256(fingerprintSeed).then(setHardwareFingerprint).catch(() => setHardwareFingerprint(""));
  }, []);

  useEffect(() => {
    const normalizedTenant = tenantName.trim();
    if (normalizedTenant.length < LIMITS.tenantName.min) {
      setTenantConfig(null);
      setTenantCheckError(null);
      setCheckingTenant(false);
      return;
    }

    const debounceId = window.setTimeout(() => {
      if (tenantCheckControllerRef.current) {
        tenantCheckControllerRef.current.abort();
      }
      const controller = new AbortController();
      tenantCheckControllerRef.current = controller;

      setCheckingTenant(true);
      setTenantCheckError(null);

      const timeout = window.setTimeout(() => controller.abort(), 4000);
      fetch(
        apiUrl(`/api/v1/tenants/signup-config?tenant_name=${encodeURIComponent(normalizedTenant)}`),
        { method: "GET", signal: controller.signal },
      )
        .then(async (res) => {
          window.clearTimeout(timeout);
          if (res.status === 404) {
            setTenantConfig(null);
            return;
          }
          if (!res.ok) {
            const msg = await res.text().catch(() => "");
            throw new Error(msg || "Unable to check tenant configuration.");
          }
          const cfg = (await res.json()) as TenantSignupConfig;
          setTenantConfig(cfg);

          // Existing tenant: lock plan to tenant selection and preselect existing packs.
          const planId = String(cfg.plan || "starter") as (typeof PLANS)[number]["id"];
          setSelectedPlan(planId);
          setWorkflowAddonSlots(Number(cfg.workflow_addon_slots || 0));
          setSelectedPacks((prev) => {
            const required = new Set((cfg.agent_packs || []).filter(Boolean));
            const merged = new Set([...(prev || []), ...required]);
            return Array.from(merged);
          });
        })
        .catch((err: any) => {
          if (err?.name === "AbortError") return;
          // Do not block signup if backend is unreachable; just show a hint.
          setTenantCheckError("Unable to verify tenant configuration right now.");
          setTenantConfig(null);
        })
        .finally(() => {
          if (tenantCheckControllerRef.current === controller) {
            tenantCheckControllerRef.current = null;
          }
          setCheckingTenant(false);
        });
    }, 350);

    return () => window.clearTimeout(debounceId);
  }, [tenantName]);

  const canGoNext = () => {
    if (step === 0) {
      return !!tenantName && !!fullName && !!email && !!password && !!confirmPassword;
    }
    if (step === 1) {
      if (checkingTenant) return false;
      return !!selectedPlan;
    }
    if (step === 2) {
      if (checkingTenant) return false;
      if (selectedPacks.length === 0) return false;
      const activePlan = PLANS.find((p) => p.id === selectedPlan);
      const maxPacks = tenantConfig ? (tenantConfig.max_agent_packs ?? null) : (activePlan?.maxPacks ?? null);
      if (maxPacks !== null && selectedPacks.length > maxPacks) return false;
      return true;
    }
    if (step === 3) {
      return !!deviceName.trim();
    }
    return true;
  };

  const validateStep0 = () => {
    const nextErrors = buildStep0Errors();
    setStep0Errors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const checkEmailAlreadyExists = async (emailInput: string) => {
    const normalizedEmail = emailInput.trim().toLowerCase();
    if (!normalizedEmail || !EMAIL_RE.test(normalizedEmail)) {
      return false;
    }
    const cached = emailAvailabilityCacheRef.current.get(normalizedEmail);
    if (cached !== undefined) {
      setLastCheckedEmail(normalizedEmail);
      setLastCheckedEmailExists(cached);
      return cached;
    }
    if (normalizedEmail === lastCheckedEmail && lastCheckedEmailExists !== null) {
      return lastCheckedEmailExists;
    }

    if (emailCheckControllerRef.current) {
      emailCheckControllerRef.current.abort();
    }
    const controller = new AbortController();
    emailCheckControllerRef.current = controller;

    setCheckingEmail(true);
    setEmailCheckError(null);
    try {
      const timeout = window.setTimeout(() => controller.abort(), 4000);
      const res = await fetch(
        apiUrl(`/api/v1/auth/email-availability?email=${encodeURIComponent(normalizedEmail)}`),
        { method: "GET", signal: controller.signal },
      );
      window.clearTimeout(timeout);
      if (!res.ok) {
        setLastCheckedEmail(normalizedEmail);
        setLastCheckedEmailExists(null);
        setEmailCheckError("Unable to verify email availability right now.");
        return false;
      }
      const payload = await res.json().catch(() => null);
      const exists = Boolean(payload?.exists);
      setLastCheckedEmail(normalizedEmail);
      setLastCheckedEmailExists(exists);
      emailAvailabilityCacheRef.current.set(normalizedEmail, exists);
      return exists;
    } catch (error: any) {
      if (error?.name === "AbortError") {
        return false;
      }
      setLastCheckedEmail(normalizedEmail);
      setLastCheckedEmailExists(null);
      setEmailCheckError("Unable to verify email availability right now.");
      return false;
    } finally {
      if (emailCheckControllerRef.current === controller) {
        emailCheckControllerRef.current = null;
        setCheckingEmail(false);
      }
    }
  };

  useEffect(() => {
    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail || !EMAIL_RE.test(normalizedEmail)) {
      setCheckingEmail(false);
      return;
    }
    const debounceId = window.setTimeout(() => {
      void checkEmailAlreadyExists(normalizedEmail).then((exists) => {
        if (exists) {
          setStep0Errors((prev) => ({
            ...prev,
            email: "This work email is already registered. Please sign in or use other email.",
          }));
        }
      });
    }, 250);
    return () => window.clearTimeout(debounceId);
  }, [email]);

  const nextStep = async () => {
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

      const exists = await checkEmailAlreadyExists(email);
      if (exists) {
        setStep0Errors((prev) => ({
          ...prev,
          email: "This work email is already registered. Please sign in or use other email.",
        }));
        toast({
          title: "Email already used",
          description: "This work email is already registered. Please sign in or use other email.",
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
      const requiredTenantPacks = new Set((tenantConfig?.agent_packs || []).filter(Boolean));
      const mergedPacks = Array.from(new Set([...(selectedPacks || []), ...requiredTenantPacks]));
      const activePlan = PLANS.find((p) => p.id === selectedPlan);
      const isExistingTenant = Boolean(tenantConfig);
      const userMetadata: Record<string, any> = {
        tenant_name: tenantName.trim(),
        full_name: fullName.trim(),
        requested_role: selectedRole,
        agent_packs: mergedPacks,
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
      };

      // Only the global-admin "create tenant" flow should send plan/limits fields.
      if (!isExistingTenant) {
        userMetadata.plan = selectedPlan;
        userMetadata.workflow_addon_slots = workflowAddonSlots;
        userMetadata.max_agent_packs = activePlan?.maxPacks ?? null;
        userMetadata.max_active_models = activePlan?.maxModels ?? null;
        userMetadata.default_model_id = null;
      }

      if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
        throw new Error("Supabase environment variables are not configured.");
      }

      // Use GoTrue signup directly so we can access DB-trigger error codes
      // (e.g. pack-limit concurrency failures with code `P0001`).
      const signupRes = await fetch(`${SUPABASE_URL}/auth/v1/signup`, {
        method: "POST",
        headers: {
          apikey: SUPABASE_ANON_KEY,
          Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: normalizedEmail,
          password,
          data: {
            ...userMetadata,
          },
        }),
      });

      const signupJson = await signupRes.json().catch(() => null);
      if (!signupRes.ok) {
        throw {
          code: signupJson?.code,
          message: signupJson?.message,
          status: signupRes.status,
        };
      }

      const signedUpUserId = signupJson?.user?.id as string | undefined;
      const accessToken = signupJson?.access_token as string | undefined;
      const refreshToken = signupJson?.refresh_token as string | undefined;

      if (accessToken && refreshToken) {
        await supabase.auth.setSession({ access_token: accessToken, refresh_token: refreshToken });
      }

      if (signedUpUserId) {
        const { error: profileError } = await supabase
          .from("app_users")
          .update({ full_name: fullName })
          .eq("user_id", signedUpUserId);
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
      const errCode = String(error?.code || "").toLowerCase();
      const rawMessage = String(error?.message || "").toLowerCase();

      let friendlyMessage =
        rawMessage.includes("already registered")
        || rawMessage.includes("already been registered")
        || rawMessage.includes("already exists")
          ? "This email is already registered. Try signing in or using password reset."
          : rawMessage.includes("password")
          ? `Password does not meet security requirements. Use ${LIMITS.password.min}-${LIMITS.password.max} characters with uppercase, lowercase, number, and special character.`
          : error?.message ?? "Something went wrong while creating your tenant.";

      // GoTrue / DB trigger failures propagate as code `P0001` with messages like:
      //   FIDEON_OS_LIMIT:PACKS Agent pack limit reached (2/1). Upgrade plan to add more packs.
      if (
        errCode === "p0001"
        && (rawMessage.includes("pack limit reached") || rawMessage.includes("fideon_os_limit:packs"))
      ) {
        if (tenantConfig?.max_agent_packs === null || tenantConfig?.max_agent_packs === undefined) {
          friendlyMessage = "Pack limit reached for this tenant. Please select fewer packs and try again.";
        } else if (tenantConfig?.remaining_pack_slots === 0) {
          friendlyMessage = "This tenant has no remaining pack slots. Please select fewer packs or upgrade the plan.";
        } else {
          friendlyMessage = `Pack limit reached for this tenant. Please select up to ${tenantConfig?.remaining_pack_slots} more pack(s).`;
        }
      }
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
                  minLength={LIMITS.tenantName.min}
                  maxLength={LIMITS.tenantName.max}
                  onChange={(e) => {
                    setTenantName(e.target.value);
                    if (step0Errors.tenantName) {
                      setStep0Errors((prev) => ({ ...prev, tenantName: undefined }));
                    }
                  }}
                  onBlur={() => {
                    if (!tenantName.trim()) {
                      setStep0Errors((prev) => ({
                        ...prev,
                        tenantName: "Tenant / Company Name is required.",
                      }));
                    } else if (tenantName.trim().length < LIMITS.tenantName.min) {
                      setStep0Errors((prev) => ({
                        ...prev,
                        tenantName: `Tenant / Company Name must be at least ${LIMITS.tenantName.min} characters.`,
                      }));
                    } else if (tenantName.trim().length > LIMITS.tenantName.max) {
                      setStep0Errors((prev) => ({
                        ...prev,
                        tenantName: `Tenant / Company Name must be ${LIMITS.tenantName.max} characters or fewer.`,
                      }));
                    }
                  }}
                  placeholder="Acme Insurance Brokers"
                  aria-invalid={Boolean(step0Errors.tenantName)}
                  className={step0Errors.tenantName ? "border-destructive focus-visible:ring-destructive" : ""}
                />
                {step0Errors.tenantName && (
                  <p className="text-xs text-destructive">{step0Errors.tenantName}</p>
                )}
                {!step0Errors.tenantName && checkingTenant && (
                  <p className="text-xs text-muted-foreground">Checking tenant configuration...</p>
                )}
                {!step0Errors.tenantName && !checkingTenant && tenantConfig && (
                  <p className="text-xs text-primary">
                    Existing tenant detected. Plan and enabled packs will be applied automatically.
                  </p>
                )}
                {!step0Errors.tenantName && !checkingTenant && tenantCheckError && (
                  <p className="text-xs text-amber-600">{tenantCheckError}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="full-name">Your Name</Label>
                <Input
                  id="full-name"
                  value={fullName}
                  minLength={LIMITS.fullName.min}
                  maxLength={LIMITS.fullName.max}
                  onChange={(e) => {
                    setFullName(e.target.value);
                    if (step0Errors.fullName) {
                      setStep0Errors((prev) => ({ ...prev, fullName: undefined }));
                    }
                  }}
                  onBlur={() => {
                    if (!fullName.trim()) {
                      setStep0Errors((prev) => ({
                        ...prev,
                        fullName: "Your name is required.",
                      }));
                    } else if (fullName.trim().length < LIMITS.fullName.min) {
                      setStep0Errors((prev) => ({
                        ...prev,
                        fullName: `Your name must be at least ${LIMITS.fullName.min} characters.`,
                      }));
                    } else if (fullName.trim().length > LIMITS.fullName.max) {
                      setStep0Errors((prev) => ({
                        ...prev,
                        fullName: `Your name must be ${LIMITS.fullName.max} characters or fewer.`,
                      }));
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
                  minLength={LIMITS.email.min}
                  maxLength={LIMITS.email.max}
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setLastCheckedEmail("");
                    setLastCheckedEmailExists(null);
                    setEmailCheckError(null);
                    if (step0Errors.email) {
                      setStep0Errors((prev) => ({ ...prev, email: undefined }));
                    }
                  }}
                  onBlur={() => {
                    const normalizedEmail = email.trim().toLowerCase();
                    const emailLocalPart = normalizedEmail.split("@")[0] || "";
                    if (!normalizedEmail) {
                      setStep0Errors((prev) => ({
                        ...prev,
                        email: "Work email is required.",
                      }));
                    } else if (
                      normalizedEmail.length < LIMITS.email.min ||
                      normalizedEmail.length > LIMITS.email.max
                    ) {
                      setStep0Errors((prev) => ({
                        ...prev,
                        email: `Work email must be ${LIMITS.email.min}-${LIMITS.email.max} characters.`,
                      }));
                    } else if (emailLocalPart.length > LIMITS.email.localPartMax) {
                      setStep0Errors((prev) => ({
                        ...prev,
                        email: `Email username must be ${LIMITS.email.localPartMax} characters or fewer.`,
                      }));
                    } else if (!EMAIL_RE.test(normalizedEmail)) {
                      setStep0Errors((prev) => ({
                        ...prev,
                        email: "Enter a valid work email address.",
                      }));
                    } else {
                      void checkEmailAlreadyExists(normalizedEmail).then((exists) => {
                        if (exists) {
                          setStep0Errors((prev) => ({
                            ...prev,
                            email: "This work email is already registered. Please sign in or use other email.",
                          }));
                        }
                      });
                    }
                  }}
                  placeholder="you@company.com"
                  aria-invalid={Boolean(step0Errors.email)}
                  className={step0Errors.email ? "border-destructive focus-visible:ring-destructive" : ""}
                />
                {step0Errors.email && (
                  <p className="text-xs text-destructive">{step0Errors.email}</p>
                )}
                {!step0Errors.email && checkingEmail && (
                  <p className="text-xs text-muted-foreground">Checking email availability...</p>
                )}
                {!step0Errors.email && !checkingEmail && emailCheckError && (
                  <p className="text-xs text-amber-600">{emailCheckError}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <PasswordInput
                  id="password"
                  minLength={LIMITS.password.min}
                  maxLength={LIMITS.password.max}
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
                  onBlur={() => {
                    if (!password) {
                      setStep0Errors((prev) => ({
                        ...prev,
                        password: "Password is required.",
                      }));
                    } else if (
                      password.length < LIMITS.password.min ||
                      password.length > LIMITS.password.max
                    ) {
                      setStep0Errors((prev) => ({
                        ...prev,
                        password: `Password must be ${LIMITS.password.min}-${LIMITS.password.max} characters.`,
                      }));
                    } else if (!PASSWORD_STRENGTH_RE.test(password)) {
                      setStep0Errors((prev) => ({
                        ...prev,
                        password:
                          "Use at least 1 uppercase, 1 lowercase, 1 number, and 1 special character.",
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
                {!step0Errors.password && (
                  <p className="text-[11px] text-muted-foreground">
                    {`Use ${LIMITS.password.min}-${LIMITS.password.max} characters with uppercase, lowercase, number, and special character.`}
                  </p>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Confirm Password</Label>
              <PasswordInput
                id="confirm-password"
                minLength={LIMITS.password.min}
                maxLength={LIMITS.password.max}
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value);
                  if (step0Errors.confirmPassword) {
                    setStep0Errors((prev) => ({ ...prev, confirmPassword: undefined }));
                  }
                }}
                onBlur={() => {
                  if (!confirmPassword) {
                    setStep0Errors((prev) => ({
                      ...prev,
                      confirmPassword: "Please confirm your password.",
                    }));
                  } else if (password !== confirmPassword) {
                    setStep0Errors((prev) => ({
                      ...prev,
                      confirmPassword: "Passwords do not match.",
                    }));
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
                {tenantConfig
                  ? "This tenant already exists. Plan is locked to the global admin selection."
                  : "You can change plans later as you scale."}
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              {PLANS.map((plan) => (
                <button
                  key={plan.id}
                  type="button"
                  onClick={() => {
                    if (tenantConfig) return;
                    setSelectedPlan(plan.id);
                    setWorkflowAddonSlots(0);
                    setSelectedPacks([]);
                  }}
                  disabled={Boolean(tenantConfig)}
                  className={`rounded-xl border p-4 text-left transition h-full ${
                    selectedPlan === plan.id
                      ? "border-primary bg-primary/5 shadow-sm"
                      : tenantConfig
                      ? "border-border opacity-50 cursor-not-allowed"
                      : "border-border hover:border-primary/40"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <h3 className="font-semibold">{plan.name}</h3>
                    {selectedPlan === plan.id && (
                      <Badge className="text-[10px]">Selected</Badge>
                    )}
                  </div>
                  <p className="text-xs font-medium text-primary mb-1">{plan.price}</p>
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

            {/* Workflow Slots Configuration */}
            {(() => {
              const activePlan = PLANS.find((p) => p.id === selectedPlan);
              if (!activePlan) return null;
              return (
                <div className="rounded-xl border p-4 space-y-3">
                  <div>
                    <h3 className="font-semibold text-sm">Workflow Slots</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {activePlan.includedSlots === null
                        ? "Unlimited workflow slots included with Enterprise."
                        : `${activePlan.includedSlots} slots included with ${activePlan.name}.`}
                      {activePlan.maxAddonSlots > 0 && " Add up to 5 extra slots at $5,000–$6,000 each."}
                    </p>
                  </div>
                  {activePlan.maxAddonSlots > 0 ? (
                    <div className="flex items-center gap-3">
                      <label htmlFor="addon-slots" className="text-xs font-medium whitespace-nowrap">
                        Additional slots (0–{activePlan.maxAddonSlots}):
                      </label>
                      <input
                        id="addon-slots"
                        type="number"
                        min={0}
                        max={activePlan.maxAddonSlots}
                        value={workflowAddonSlots}
                        onChange={(e) =>
                          setWorkflowAddonSlots(
                            Math.min(activePlan.maxAddonSlots, Math.max(0, Number(e.target.value)))
                          )
                        }
                        className="w-20 rounded-md border border-input bg-background px-3 py-1.5 text-sm"
                      />
                      <span className="text-xs text-muted-foreground">
                        Total: {activePlan.includedSlots! + workflowAddonSlots} slots
                      </span>
                    </div>
                  ) : (
                    <p className="text-xs text-primary font-medium">No additional slots needed — unlimited included.</p>
                  )}
                </div>
              );
            })()}
          </div>
        );
      case 2: {
        const activePlan = PLANS.find((p) => p.id === selectedPlan);
        const maxPacks   = tenantConfig ? (tenantConfig.max_agent_packs ?? null) : (activePlan?.maxPacks ?? null);
        const maxModels  = activePlan?.maxModels ?? null;
        const atPackLimit = maxPacks !== null && selectedPacks.length >= maxPacks;
        const requiredTenantPacks = new Set((tenantConfig?.agent_packs || []).filter(Boolean));
        const remainingSlots =
          maxPacks === null ? null : Math.max(0, maxPacks - requiredTenantPacks.size);
        return (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-semibold flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                Select Agent Packs
              </h2>
              <p className="text-sm text-muted-foreground">
                {maxPacks === null
                  ? "Choose any agent packs to activate — unlimited on Enterprise."
                  : tenantConfig
                  ? `This tenant can have up to ${maxPacks} agent pack${maxPacks > 1 ? "s" : ""}. ${requiredTenantPacks.size} already selected by the global admin.${remainingSlots !== null ? ` You can add ${remainingSlots} more.` : ""}`
                  : `Your ${activePlan?.name} plan includes up to ${maxPacks} agent pack${maxPacks > 1 ? "s" : ""} and ${maxModels} active AI models.`}
              </p>
            </div>

            {/* Pack counter */}
            <div className="flex items-center justify-between rounded-lg border bg-muted/30 px-4 py-2">
              <span className="text-xs text-muted-foreground">Packs selected</span>
              <span className={`text-sm font-semibold ${atPackLimit ? "text-amber-500" : "text-primary"}`}>
                {selectedPacks.length}
                {maxPacks !== null && ` / ${maxPacks}`}
              </span>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {AGENT_PACKS.map((pack) => {
                const selected  = selectedPacks.includes(pack.id);
                const required  = requiredTenantPacks.has(pack.id);
                const tenantLockedOut = Boolean(tenantConfig) && maxPacks !== null && remainingSlots === 0 && !required;
                const disabled  = required || tenantLockedOut || (!selected && atPackLimit);
                return (
                  <button
                    key={pack.id}
                    type="button"
                    disabled={disabled}
                    onClick={() =>
                      setSelectedPacks((prev) =>
                        required ? prev : selected ? prev.filter((id) => id !== pack.id) : [...prev, pack.id]
                      )
                    }
                    className={`rounded-xl border p-4 text-left transition h-full ${
                      selected
                        ? "border-primary bg-primary/5 shadow-sm"
                        : disabled
                        ? "border-border opacity-40 grayscale cursor-not-allowed"
                        : "border-border hover:border-primary/40"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-semibold text-sm">{pack.name}</h3>
                      {selected && <CheckCircle2 className="h-4 w-4 text-primary shrink-0" />}
                    </div>
                    <p className="text-xs text-muted-foreground">{pack.description}</p>
                    {tenantConfig && required && (
                      <p className="text-[10px] text-primary mt-2 pt-2 border-t border-border/50">
                        Enabled for this tenant (chosen by global admin)
                      </p>
                    )}
                    {maxModels !== null && (
                      <p className="text-[10px] text-muted-foreground mt-2 pt-2 border-t border-border/50">
                        Up to {maxModels} active models with this plan
                      </p>
                    )}
                  </button>
                );
              })}
            </div>

            {selectedPacks.length === 0 && (
              <p className="text-xs text-destructive">Select at least one agent pack to continue.</p>
            )}
            {atPackLimit && (
              <p className="text-xs text-amber-500">
                Pack limit reached for {activePlan?.name} ({maxPacks} pack{maxPacks !== 1 ? "s" : ""}).
                Upgrade to Professional or Enterprise to add more.
              </p>
            )}
          </div>
        );
      }
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
                  <li>We store role, tenant name, plan, agent packs, and device metadata.</li>
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
            {STEP_META.map((stepItem) => {
              const i = stepItem.index;
              const active = step === i;
              const isCompleted = step > i || completed;
              return (
                <div key={stepItem.label} className="flex-1 flex items-center gap-2">
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
                    {stepItem.label}
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
                <div className="flex flex-col items-end gap-1">
                  <Button
                    type="button"
                    onClick={nextStep}
                    disabled={loading || completed}
                    className="flex items-center gap-1 text-xs md:text-sm"
                  >
                    Next
                    <ChevronRight className="h-3 w-3" />
                  </Button>
                  {step === 0 && !canGoNext() && (
                    <p className="text-[11px] text-destructive text-right">
                      Fill all required fields to continue.
                    </p>
                  )}
                </div>
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
