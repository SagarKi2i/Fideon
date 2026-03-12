import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import type { Database } from "@/integrations/supabase/types";
import { useToast } from "@/hooks/use-toast";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, ChevronLeft, ChevronRight, Cpu, MonitorSmartphone, Shield, Sparkles, User } from "lucide-react";

type WizardStep = 0 | 1 | 2 | 3;
type AppRole = Database["public"]["Enums"]["app_role"];

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
  const [showAllModels, setShowAllModels] = useState(false);

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
    return true;
  };

  const nextStep = () => {
    if (!canGoNext()) {
      toast({
        title: "Missing information",
        description: "Please complete this step before continuing.",
        variant: "destructive",
      });
      return;
    }
    if (step === 0) {
      if (password.length < 8) {
        toast({
          title: "Password too short",
          description: "Use at least 8 characters.",
          variant: "destructive",
        });
        return;
      }
      if (password !== confirmPassword) {
        toast({
          title: "Passwords do not match",
          description: "Please enter the same password in both fields.",
          variant: "destructive",
        });
        return;
      }
    }
    setStep((s) => (s < 3 ? ((s + 1) as WizardStep) : s));
  };

  const prevStep = () => {
    setStep((s) => {
      if (s > 0) {
        return ((s - 1) as WizardStep);
      }
      navigate("/auth");
      return s;
    });
  };

  const handleComplete = async () => {
    if (!canGoNext()) return;
    setLoading(true);
    try {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            tenant_name: tenantName,
            full_name: fullName,
            requested_role: selectedRole,
            plan: selectedPlan,
            default_model_id: selectedModelId,
            device_name: deviceName,
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
      toast({
        title: "Onboarding failed",
        description: error?.message ?? "Something went wrong while creating your tenant.",
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
                  onChange={(e) => setTenantName(e.target.value)}
                  placeholder="Acme Insurance Brokers"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="full-name">Your Name</Label>
                <Input
                  id="full-name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jane Doe"
                />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="email">Work Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Confirm Password</Label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter password"
              />
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
                  disabled={!canGoNext() || loading || completed}
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
