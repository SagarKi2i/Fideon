import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { Shield, Lock, Cpu } from "lucide-react";
import { FideonLogo } from "@/components/FideonLogo";
import privateTenantBg from "@/assets/private-ai-tenant-bg.jpg";

export default function Auth() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();
  const navigate = useNavigate();

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const { data: signInData, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) throw error;

      if (signInData.user) {
        const { data: roleData } = await supabase
          .from('user_roles')
          .select('role')
          .eq('user_id', signInData.user.id)
          .maybeSingle();

        if (roleData?.role === 'admin') {
          navigate("/admin");
        } else {
          navigate("/");
        }
      } else {
        navigate("/");
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

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
                <h1 className="text-4xl font-bold text-foreground">Fideon Fabric</h1>
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
                Welcome to Fideon Fabric
              </CardTitle>
              <CardDescription className="text-center">
                Sign in to access your Private AI Tenant
              </CardDescription>
            </CardHeader>
            <CardContent>
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
              </form>
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
