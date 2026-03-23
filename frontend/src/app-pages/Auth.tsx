import React from "react";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { Provider } from "@supabase/supabase-js";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { Shield, Lock, Cpu, KeyRound, Mail } from "lucide-react";
import { FideonLogo } from "@/components/FideonLogo";
import { safeLog } from "@/logger";
import privateTenantBg from "@/assets/private-ai-tenant-bg.jpg";
import { computeAuditIntegrityHash } from "@/lib/auditHash";
import { apiUrl } from "@/lib/apiBaseUrl";
import { buildApiRequestError, readJsonSafe } from "@/lib/httpErrors";

type AuthView = "signin" | "forgot" | "reset";
type AppRole = "global_admin" | "admin" | "user" | "viewer" | "guest";

const VALID_APP_ROLES: AppRole[] = ["global_admin", "admin", "user", "viewer", "guest"];

function isAppRole(value: unknown): value is AppRole {
  return typeof value === "string" && VALID_APP_ROLES.includes(value as AppRole);
}

async function resolveEffectiveRole(userId: string): Promise<AppRole> {
  const { data: roleData, error: roleError } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", userId)
    .maybeSingle();

  if (!roleError && isAppRole(roleData?.role)) {
    return roleData.role;
  }

  try {
    const { data: sessionData } = await supabase.auth.getSession();
    const token = sessionData.session?.access_token;
    if (token) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);
      try {
        const res = await fetch(apiUrl("/api/settings/profile"), {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });
        clearTimeout(timeout);
        if (res.ok) {
          const payload = await readJsonSafe(res);
          const backendRole = payload?.profile?.role;
          if (isAppRole(backendRole)) {
            return backendRole;
          }
        } else if (res.status === 401 || res.status === 403) {
          const payload = await readJsonSafe(res);
          throw buildApiRequestError(res, payload, "Unable to resolve user role");
        }
      } finally {
        clearTimeout(timeout);
      }
    }
  } catch (backendError) {
    safeLog.error("auth_role_backend_fallback_error", {
      user_id: userId,
      error: backendError instanceof Error ? backendError.message : String(backendError),
    });
  }

  return "user";
}

export default function Auth() {
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();
  const authEnableSso = process.env.NEXT_PUBLIC_AUTH_ENABLE_SSO === "true";
  const authEnableMfa = process.env.NEXT_PUBLIC_AUTH_ENABLE_MFA === "true";
  const ssoProviderCsv = process.env.NEXT_PUBLIC_AUTH_SSO_PROVIDERS || "";
  const allowedProviders = useMemo(
    () =>
      ssoProviderCsv
        .split(",")
        .map((s) => s.trim().toLowerCase())
        .filter((s): s is Provider => ["google", "github", "azure"].includes(s)),
    [ssoProviderCsv]
  );

  const [view, setView] = useState<AuthView>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const [activeUserId, setActiveUserId] = useState<string | null>(null);

  const [factors, setFactors] = useState<Array<{ id: string; label: string }>>([]);
  const [factorId, setFactorId] = useState<string>("");
  const [challengeId, setChallengeId] = useState<string>("");
  const [totpCode, setTotpCode] = useState<string>("");
  const [qrMarkup, setQrMarkup] = useState<string>("");

  useEffect(() => {
    const hash = window.location.hash.startsWith("#")
      ? window.location.hash.slice(1)
      : window.location.hash;
    const hashParams = new URLSearchParams(hash);
    if (hashParams.get("type") === "recovery") {
      setView("reset");
    }

    const bootstrap = async () => {
      const { data } = await supabase.auth.getUser();
      setActiveUserId(data.user?.id ?? null);
    };
    bootstrap();

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      setActiveUserId(session?.user?.id ?? null);
      if (event === "PASSWORD_RECOVERY") {
        setView("reset");
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const pid = params.get("pid");
    const code = params.get("code");
    const pair = params.get("pair");
    if (pid && code && pair === "1") {
      navigate(`/device-link?pid=${encodeURIComponent(pid)}&code=${encodeURIComponent(code)}`, { replace: true });
    }
  }, [location.search, navigate]);

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      safeLog.info("auth_signin_attempt", { email });
      const { data: signInData, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) throw error;

      if (signInData.user) {
        const effectiveRole = await resolveEffectiveRole(signInData.user.id);

        safeLog.info("auth_signin_success", {
          user_id: signInData.user.id,
          role: effectiveRole,
        });

        // Insert audit log row (Supabase RLS controls visibility)
        try {
          const createdAt = new Date().toISOString();
          const integrity_hash = await computeAuditIntegrityHash({
            user_id: signInData.user.id,
            role: effectiveRole,
            event: "login",
            action_code: "E",
            outcome_code: 0,
            resource_type: "auth_session",
            resource_id: null,
            created_at: createdAt,
          });

          await (supabase as any).from("auth_audit").insert({
            user_id: signInData.user.id,
            email,
            role: effectiveRole,
            event: "login",
            action_code: "E",          // Execute (auth workflow)
            outcome_code: 0,           // Success
            resource_type: "auth_session",
            resource_id: null,         // null for auth_session events (no specific resource)
            created_at: createdAt,
            integrity_hash,
          });
        } catch (auditError) {
          safeLog.error("auth_audit_insert_error", {
            error:
              auditError instanceof Error ? auditError.message : String(auditError),
          });
        }

        if (effectiveRole === "admin" || effectiveRole === "global_admin") {
          navigate("/admin");
        } else {
          navigate("/");
        }
      } else {
        safeLog.info("auth_signin_success_no_user", { email });
        navigate("/");
      }
    } catch (error: any) {
      // ATNA login_failed event (action_code: E, outcome_code: 8 = Serious failure).
      // Cannot insert into auth_audit from client — no authenticated session exists
      // after a failed login (auth.uid() is null, RLS would reject the insert).
      // Logged here via structlog as the server-side audit trail for this event.
      safeLog.error("login_failed", {
        email,
        event: "login_failed",
        action_code: "E",
        outcome_code: 8,
        resource_type: "auth_session",
        resource_id: null,
        error: error.message,
      });
      const rawMsg: string = error.message ?? "";
      let friendlyMsg = rawMsg;
      if (/invalid login credentials/i.test(rawMsg)) {
        const { count } = await supabase
          .from("app_users")
          .select("user_id", { count: "exact", head: true })
          .eq("email", email.trim().toLowerCase());
        friendlyMsg =
          count === 0
            ? "No account found for this email."
            : "Password is incorrect. Please check your details or contact your admin.";
      }
      toast({
        title: "Sign in failed",
        description: friendlyMsg,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const redirectTo = `${window.location.origin}/auth`;
      const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo });
      if (error) throw error;
      toast({
        title: "Reset email sent",
        description: "Check your inbox for the password reset link.",
      });
      setView("signin");
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to send reset email",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      toast({
        title: "Password too short",
        description: "Use at least 8 characters.",
        variant: "destructive",
      });
      return;
    }
    if (newPassword !== confirmPassword) {
      toast({
        title: "Passwords do not match",
        description: "Please enter the same password in both fields.",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);
    try {
      const { error } = await supabase.auth.updateUser({ password: newPassword });
      if (error) throw error;
      toast({
        title: "Password updated",
        description: "Sign in with your new password.",
      });
      setView("signin");
      setPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error: any) {
      toast({
        title: "Reset failed",
        description: error.message || "Could not update password.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleOAuthSignIn = async (provider: Provider) => {
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider,
        options: { redirectTo: `${window.location.origin}/auth` },
      });
      if (error) throw error;
    } catch (error: any) {
      toast({
        title: "SSO sign-in failed",
        description: error.message || `Could not sign in with ${provider}.`,
        variant: "destructive",
      });
    }
  };

  const loadMfaFactors = async () => {
    try {
      const { data, error } = await supabase.auth.mfa.listFactors();
      if (error) throw error;
      const allTotp = [...(data?.all ?? [])]
        .filter((f: any) => f.factor_type === "totp")
        .map((f: any) => ({ id: f.id as string, label: f.friendly_name || "Authenticator App" }));
      setFactors(allTotp);
      if (!factorId && allTotp.length > 0) {
        setFactorId(allTotp[0].id);
      }
    } catch (error: any) {
      toast({
        title: "MFA status unavailable",
        description: error.message || "Could not load MFA factors.",
        variant: "destructive",
      });
    }
  };

  const handleMfaEnroll = async () => {
    try {
      const { data, error } = await supabase.auth.mfa.enroll({
        factorType: "totp",
        friendlyName: "Authenticator App",
      });
      if (error) throw error;
      setFactorId(data.id);
      setQrMarkup((data.totp as any)?.qr_code || "");
      toast({
        title: "MFA enrolled",
        description: "Scan the QR code and verify with a TOTP code.",
      });
      await loadMfaFactors();
    } catch (error: any) {
      toast({
        title: "MFA enroll failed",
        description: error.message || "Could not enroll MFA.",
        variant: "destructive",
      });
    }
  };

  const handleMfaChallenge = async () => {
    if (!factorId) {
      toast({ title: "Select a factor", description: "Choose an enrolled factor first.", variant: "destructive" });
      return;
    }
    try {
      const { data, error } = await supabase.auth.mfa.challenge({ factorId });
      if (error) throw error;
      setChallengeId(data.id);
      toast({ title: "Challenge created", description: "Enter the current TOTP code to verify." });
    } catch (error: any) {
      toast({
        title: "Challenge failed",
        description: error.message || "Could not create MFA challenge.",
        variant: "destructive",
      });
    }
  };

  const handleMfaVerify = async () => {
    if (!factorId || !challengeId || !totpCode) {
      toast({
        title: "Missing details",
        description: "Factor, challenge, and code are required.",
        variant: "destructive",
      });
      return;
    }
    try {
      const { error } = await supabase.auth.mfa.verify({
        factorId,
        challengeId,
        code: totpCode,
      });
      if (error) throw error;
      setTotpCode("");
      setChallengeId("");
      toast({ title: "MFA verified", description: "Your factor is now active." });
    } catch (error: any) {
      toast({
        title: "Verification failed",
        description: error.message || "Invalid TOTP code.",
        variant: "destructive",
      });
    }
  };

  const handleMfaUnenroll = async () => {
    if (!factorId) {
      return;
    }
    try {
      const { error } = await supabase.auth.mfa.unenroll({ factorId });
      if (error) throw error;
      setFactorId("");
      setChallengeId("");
      setTotpCode("");
      setQrMarkup("");
      toast({ title: "MFA removed", description: "Selected factor was unenrolled." });
      await loadMfaFactors();
    } catch (error: any) {
      toast({
        title: "Unenroll failed",
        description: error.message || "Could not remove MFA factor.",
        variant: "destructive",
      });
    }
  };

  const signInView = (
    <form onSubmit={handleSignIn} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="signin-email">Email</Label>
        <Input
          id="signin-email"
          type="email"
          placeholder="your@email.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="bg-background/50"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="signin-password">Password</Label>
        <Input
          id="signin-password"
          type="password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="bg-background/50"
        />
      </div>
      <Button
        type="submit"
        className="w-full bg-gradient-to-r from-primary to-primary/80 hover:opacity-90 transition-opacity"
        disabled={loading}
      >
        {loading ? "Signing in..." : "Sign In"}
      </Button>
      <button
        type="button"
        onClick={() => setView("forgot")}
        className="w-full text-sm text-primary underline-offset-4 hover:underline bg-transparent border-none cursor-pointer py-1"
      >
        Forgot password?
      </button>
      <Button type="button" variant="outline" className="w-full" onClick={() => navigate("/signup")}>
        Create new account
      </Button>
    </form>
  );

  const forgotView = (
    <form onSubmit={handleForgotPassword} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="forgot-email">Work Email</Label>
        <Input
          id="forgot-email"
          type="email"
          placeholder="your@email.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="bg-background/50"
        />
      </div>
      <Button type="submit" className="w-full" disabled={loading}>
        {loading ? "Sending..." : "Send reset link"}
      </Button>
      <button
        type="button"
        onClick={() => setView("signin")}
        className="w-full text-sm text-primary underline-offset-4 hover:underline bg-transparent border-none cursor-pointer py-1"
      >
        Back to sign in
      </button>
    </form>
  );

  const resetView = (
    <form onSubmit={handleResetPassword} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="reset-password">New Password</Label>
        <Input
          id="reset-password"
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          minLength={8}
          required
          className="bg-background/50"
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="reset-password-confirm">Confirm Password</Label>
        <Input
          id="reset-password-confirm"
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          minLength={8}
          required
          className="bg-background/50"
        />
      </div>
      <Button type="submit" className="w-full" disabled={loading}>
        {loading ? "Updating..." : "Update password"}
      </Button>
      <button
        type="button"
        onClick={() => setView("signin")}
        className="w-full text-sm text-primary underline-offset-4 hover:underline bg-transparent border-none cursor-pointer py-1"
      >
        Back to sign in
      </button>
    </form>
  );

  return (
    <div className="min-h-screen relative flex items-center justify-center p-4 overflow-hidden">
      <div 
        className="absolute inset-0 bg-cover bg-center bg-no-repeat"
        style={{ backgroundImage: `url(${privateTenantBg})` }}
      />
      <div className="absolute inset-0 bg-gradient-to-br from-background/95 via-background/90 to-background/95 backdrop-blur-sm" />
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/20 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl animate-pulse delay-1000" />
      </div>

      <div className="relative z-10 w-full max-w-6xl grid lg:grid-cols-2 gap-8 items-center">
        {/* Left side - Branding */}
        <div className="hidden lg:flex flex-col space-y-8 animate-fade-in">
          <div className="space-y-4">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-3 rounded-xl bg-primary/10 backdrop-blur-sm border border-primary/20">
                <FideonLogo size={40} />
              </div>
              <div>
                <h1 className="text-4xl font-bold text-foreground">Fideon OS</h1>
                <p className="text-lg text-muted-foreground">AI for Insurance</p>
              </div>
            </div>
            
            <h2 className="text-5xl font-bold text-foreground leading-tight">
              Enterprise-Grade
              <span className="block bg-gradient-to-r from-primary via-primary/80 to-primary/60 bg-clip-text text-transparent">
                Private AI Infrastructure
              </span>
            </h2>
            
            <p className="text-xl text-muted-foreground">
              Secure, scalable, and fully managed AI model deployment at the edge
            </p>
          </div>

          <div className="space-y-4">
            <div className="flex items-start gap-4 p-4 rounded-lg bg-card/50 backdrop-blur-sm border border-border/50 hover:bg-card/70 transition-all duration-300">
              <div className="p-2 rounded-lg bg-primary/10">
                <Shield className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground mb-1">Enterprise Security</h3>
                <p className="text-sm text-muted-foreground">End-to-end encryption and compliance-ready infrastructure</p>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 rounded-lg bg-card/50 backdrop-blur-sm border border-border/50 hover:bg-card/70 transition-all duration-300">
              <div className="p-2 rounded-lg bg-primary/10">
                <Lock className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground mb-1">Private Deployment</h3>
                <p className="text-sm text-muted-foreground">Your data never leaves your infrastructure</p>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 rounded-lg bg-card/50 backdrop-blur-sm border border-border/50 hover:bg-card/70 transition-all duration-300">
              <div className="p-2 rounded-lg bg-primary/10">
                <Cpu className="h-6 w-6 text-primary" />
              </div>
              <div>
                <h3 className="font-semibold text-foreground mb-1">Edge Computing</h3>
                <p className="text-sm text-muted-foreground">Deploy AI models closer to your users</p>
              </div>
            </div>
          </div>
        </div>

        {/* Right side - Sign In Only */}
        <div className="animate-scale-in">
          <Card className="w-full backdrop-blur-xl bg-card/80 border-border/50 shadow-2xl">
            <CardHeader className="space-y-4">
              <div className="flex justify-center lg:hidden">
                <div className="p-3 rounded-xl bg-primary/10 backdrop-blur-sm border border-primary/20">
                  <FideonLogo size={40} />
                </div>
              </div>
              <CardTitle className="text-2xl lg:text-3xl text-center text-foreground">
                Welcome to Fideon OS
              </CardTitle>
              <CardDescription className="text-center">
                {view === "signin" && "Sign in to access your Private AI Tenant"}
                {view === "forgot" && "Request a secure password reset link"}
                {view === "reset" && "Set a new password for your account"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {view === "signin" && signInView}
              {view === "forgot" && forgotView}
              {view === "reset" && resetView}

              {authEnableSso && allowedProviders.length > 0 && view === "signin" && (
                <div className="mt-6 space-y-2">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Mail className="h-3.5 w-3.5" />
                    Single sign-on
                  </div>
                  <div className="grid grid-cols-1 gap-2">
                    {allowedProviders.map((provider) => (
                      <Button
                        key={provider}
                        type="button"
                        variant="outline"
                        className="w-full"
                        onClick={() => handleOAuthSignIn(provider)}
                      >
                        Continue with {provider[0].toUpperCase() + provider.slice(1)}
                      </Button>
                    ))}
                  </div>
                </div>
              )}

              {authEnableMfa && (
                <div className="mt-6 rounded-lg border border-border/60 bg-background/40 p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <KeyRound className="h-4 w-4 text-primary" />
                    <p className="text-sm font-medium">MFA (TOTP) setup</p>
                  </div>
                  {!activeUserId ? (
                    <p className="text-xs text-muted-foreground">Sign in first to enroll and verify MFA factors.</p>
                  ) : (
                    <>
                      <div className="grid grid-cols-2 gap-2">
                        <Button type="button" variant="outline" onClick={loadMfaFactors}>
                          Load factors
                        </Button>
                        <Button type="button" variant="outline" onClick={handleMfaEnroll}>
                          Enroll new factor
                        </Button>
                      </div>
                      {factors.length > 0 && (
                        <div className="space-y-2">
                          <Label htmlFor="mfa-factor-id">Factor</Label>
                          <select
                            id="mfa-factor-id"
                            value={factorId}
                            onChange={(e) => setFactorId(e.target.value)}
                            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                          >
                            {factors.map((f) => (
                              <option key={f.id} value={f.id}>{f.label}</option>
                            ))}
                          </select>
                        </div>
                      )}
                      <div className="grid grid-cols-2 gap-2">
                        <Button type="button" variant="outline" onClick={handleMfaChallenge}>
                          Create challenge
                        </Button>
                        <Button type="button" variant="outline" onClick={handleMfaUnenroll}>
                          Unenroll factor
                        </Button>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="mfa-code">TOTP Code</Label>
                        <Input
                          id="mfa-code"
                          placeholder="123456"
                          value={totpCode}
                          onChange={(e) => setTotpCode(e.target.value)}
                        />
                      </div>
                      <Button type="button" className="w-full" onClick={handleMfaVerify}>
                        Verify challenge
                      </Button>
                      {qrMarkup && (
                        <div className="rounded border border-border/60 bg-background p-3">
                          <p className="text-xs text-muted-foreground mb-2">Scan this QR in your authenticator app</p>
                          <div dangerouslySetInnerHTML={{ __html: qrMarkup }} />
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
              <p className="text-xs text-muted-foreground text-center mt-4">
                Account access is managed by your administrator
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
