import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ChevronLeft, ChevronRight, Cloud, Zap, Shield, TrendingUp, Users, Boxes, Network, Sparkles, Download, Lock, Globe, Server, Target, Rocket, CheckCircle, Clock, Cog, Layers, MonitorSmartphone, GitBranch, ArrowRight, Brain, FileText, GraduationCap, Briefcase, Wrench, ListChecks } from "lucide-react";
import { toast } from "sonner";

const slides = [
  {
    id: 1,
    title: "Fideon Fabric",
    subtitle: "Enterprise AI Infrastructure at the Edge",
    content: (
      <div className="flex flex-col items-center justify-center h-full space-y-8">
        <div className="text-center space-y-4">
          <div className="flex justify-center mb-6">
            <div className="relative">
              <div className="absolute inset-0 bg-primary/20 blur-3xl rounded-full"></div>
              <Boxes className="w-32 h-32 text-primary relative" />
            </div>
          </div>
          <h1 className="text-7xl font-bold bg-gradient-to-r from-primary via-primary/80 to-primary/60 bg-clip-text text-transparent">
            Fideon Fabric
          </h1>
          <p className="text-3xl text-muted-foreground font-light">
            Private AI Tenant Infrastructure for Enterprise
          </p>
          <p className="text-xl text-muted-foreground/60 max-w-2xl mx-auto mt-4">
            Deploy domain-specific AI models on-premise with complete data sovereignty while maintaining cloud scalability
          </p>
        </div>
      </div>
    ),
  },
  {
    id: 2,
    title: "The Problem",
    subtitle: "Enterprise AI Adoption Barriers",
    content: (
      <div className="grid grid-cols-2 gap-8 h-full">
        <Card className="p-8 bg-destructive/5 border-destructive/20">
          <h3 className="text-2xl font-bold mb-4 text-destructive">Data Privacy Concerns</h3>
          <p className="text-lg text-muted-foreground">
            87% of enterprises can't use cloud AI due to regulatory requirements (GDPR, HIPAA, SOC2) and sensitive data constraints
          </p>
        </Card>
        <Card className="p-8 bg-destructive/5 border-destructive/20">
          <h3 className="text-2xl font-bold mb-4 text-destructive">Generic Models Fall Short</h3>
          <p className="text-lg text-muted-foreground">
            General-purpose AI models lack the domain expertise required for specialized industries like insurance, healthcare, and finance
          </p>
        </Card>
        <Card className="p-8 bg-destructive/5 border-destructive/20">
          <h3 className="text-2xl font-bold mb-4 text-destructive">High Latency & Costs</h3>
          <p className="text-lg text-muted-foreground">
            Cloud API calls result in unpredictable costs ($0.01-$0.10 per request) and latency issues for real-time applications
          </p>
        </Card>
        <Card className="p-8 bg-destructive/5 border-destructive/20">
          <h3 className="text-2xl font-bold mb-4 text-destructive">Complex Infrastructure</h3>
          <p className="text-lg text-muted-foreground">
            Deploying and managing local AI models requires extensive DevOps expertise, costing enterprises $200K+ annually
          </p>
        </Card>
      </div>
    ),
  },
  {
    id: 3,
    title: "Our Solution",
    subtitle: "Hybrid Private AI Tenant Platform",
    content: (
      <div className="flex flex-col justify-center h-full space-y-12">
        <div className="grid grid-cols-3 gap-6">
          <Card className="p-6 bg-primary/5 border-primary/20 text-center">
            <Cloud className="w-16 h-16 mx-auto mb-4 text-primary" />
            <h3 className="text-xl font-bold mb-2">Cloud Management</h3>
            <p className="text-muted-foreground">
              Centralized control plane for model distribution, monitoring, and orchestration
            </p>
          </Card>
          <Card className="p-6 bg-primary/5 border-primary/20 text-center">
            <Lock className="w-16 h-16 mx-auto mb-4 text-primary" />
            <h3 className="text-xl font-bold mb-2">Private Tenant</h3>
            <p className="text-muted-foreground">
              Isolated AI infrastructure running on-premise with complete data sovereignty
            </p>
          </Card>
          <Card className="p-6 bg-primary/5 border-primary/20 text-center">
            <Sparkles className="w-16 h-16 mx-auto mb-4 text-primary" />
            <h3 className="text-xl font-bold mb-2">Domain Expertise</h3>
            <p className="text-muted-foreground">
              Pre-trained models for insurance, healthcare, banking, legal, and travel
            </p>
          </Card>
        </div>
        <div className="text-center max-w-3xl mx-auto">
          <p className="text-2xl text-muted-foreground font-light">
            One platform to discover, deploy, and manage domain-specific AI models with enterprise-grade security and zero data leakage
          </p>
        </div>
      </div>
    ),
  },
  {
    id: 4,
    title: "Private AI Tenant Architecture",
    subtitle: "Complete Data Sovereignty with Private Cloud Convenience",
    content: (
      <div className="flex flex-col justify-center h-full space-y-8">
        <div className="grid grid-cols-2 gap-8">
          <Card className="p-8 bg-primary/5 border-primary/20">
            <div className="flex items-start space-x-4 mb-6">
              <Server className="w-12 h-12 text-primary" />
              <div>
                <h3 className="text-2xl font-bold mb-2">On-Premise Deployment</h3>
                <p className="text-muted-foreground text-lg">
                  AI models run entirely within your infrastructure. Data never leaves your network.
                </p>
              </div>
            </div>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex items-start">
                <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
                <span>100% data sovereignty and compliance</span>
              </li>
              <li className="flex items-start">
                <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
                <span>Zero latency for real-time inference</span>
              </li>
              <li className="flex items-start">
                <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
                <span>Works with air-gapped networks</span>
              </li>
            </ul>
          </Card>
          <Card className="p-8 bg-primary/5 border-primary/20">
            <div className="flex items-start space-x-4 mb-6">
              <Globe className="w-12 h-12 text-primary" />
              <div>
                <h3 className="text-2xl font-bold mb-2">Cloud Management</h3>
                <p className="text-muted-foreground text-lg">
                  Centralized control and monitoring without touching your sensitive data.
                </p>
              </div>
            </div>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex items-start">
                <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
                <span>Automatic model updates and patches</span>
              </li>
              <li className="flex items-start">
                <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
                <span>Device health monitoring and alerts</span>
              </li>
              <li className="flex items-start">
                <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
                <span>Usage analytics and cost tracking</span>
              </li>
            </ul>
          </Card>
        </div>
        <Card className="p-6 bg-accent/10 border-accent/20 text-center">
          <p className="text-xl font-semibold">
            <Lock className="w-6 h-6 inline mr-2" />
            Your data stays private. Our platform stays powerful.
          </p>
        </Card>
      </div>
    ),
  },
  {
    id: 5,
    title: "Key Features",
    subtitle: "Built for Enterprise Scale",
    content: (
      <div className="grid grid-cols-2 gap-6 h-full">
        <Card className="p-6 border-primary/20">
          <div className="flex items-start space-x-4">
            <div className="p-3 rounded-lg bg-primary/10">
              <Boxes className="w-8 h-8 text-primary" />
            </div>
            <div>
              <h3 className="text-xl font-bold mb-2">AI Model Marketplace</h3>
              <p className="text-muted-foreground">
                Curated library of 50+ domain-specific models across 5 industries with one-click activation
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-6 border-primary/20">
          <div className="flex items-start space-x-4">
            <div className="p-3 rounded-lg bg-primary/10">
              <Network className="w-8 h-8 text-primary" />
            </div>
            <div>
              <h3 className="text-xl font-bold mb-2">Hybrid Deployment</h3>
              <p className="text-muted-foreground">
                Seamlessly run models in cloud or on-premise with automatic synchronization and failover
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-6 border-primary/20">
          <div className="flex items-start space-x-4">
            <div className="p-3 rounded-lg bg-primary/10">
              <Shield className="w-8 h-8 text-primary" />
            </div>
            <div>
              <h3 className="text-xl font-bold mb-2">Device Management</h3>
              <p className="text-muted-foreground">
                Register, monitor, and control AI inference devices with secure token-based authentication
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-6 border-primary/20">
          <div className="flex items-start space-x-4">
            <div className="p-3 rounded-lg bg-primary/10">
              <Zap className="w-8 h-8 text-primary" />
            </div>
            <div>
              <h3 className="text-xl font-bold mb-2">Model Playground</h3>
              <p className="text-muted-foreground">
                Test and validate models before deployment with specialized interfaces for each domain
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-6 border-primary/20">
          <div className="flex items-start space-x-4">
            <div className="p-3 rounded-lg bg-primary/10">
              <Users className="w-8 h-8 text-primary" />
            </div>
            <div>
              <h3 className="text-xl font-bold mb-2">Role-Based Access</h3>
              <p className="text-muted-foreground">
                Enterprise-grade authentication with granular permissions and multi-user support
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-6 border-primary/20">
          <div className="flex items-start space-x-4">
            <div className="p-3 rounded-lg bg-primary/10">
              <Cloud className="w-8 h-8 text-primary" />
            </div>
            <div>
              <h3 className="text-xl font-bold mb-2">Document Processing</h3>
              <p className="text-muted-foreground">
                Upload, store, and analyze documents with AI-powered insights and policy comparisons
              </p>
            </div>
          </div>
        </Card>
      </div>
    ),
  },
  {
    id: 6,
    title: "Platform Dashboard",
    subtitle: "Intuitive Management Interface",
    content: (
      <div className="flex flex-col justify-center h-full space-y-6">
        <Card className="p-6 bg-muted/30 border-primary/20">
          <h3 className="text-xl font-bold mb-4">Central Control Panel</h3>
          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="p-4 bg-background rounded-lg">
              <p className="text-3xl font-bold text-primary">127</p>
              <p className="text-sm text-muted-foreground">Active Devices</p>
            </div>
            <div className="p-4 bg-background rounded-lg">
              <p className="text-3xl font-bold text-primary">24</p>
              <p className="text-sm text-muted-foreground">Deployed Models</p>
            </div>
            <div className="p-4 bg-background rounded-lg">
              <p className="text-3xl font-bold text-primary">1.2M</p>
              <p className="text-sm text-muted-foreground">Inferences/Day</p>
            </div>
          </div>
        </Card>
        <div className="grid grid-cols-2 gap-6">
          <Card className="p-6 border-primary/20">
            <h3 className="text-lg font-bold mb-3">📊 Real-Time Monitoring</h3>
            <ul className="space-y-2 text-muted-foreground text-sm">
              <li>• Device health and performance metrics</li>
              <li>• Model inference latency tracking</li>
              <li>• Resource utilization dashboards</li>
              <li>• Automated alerting system</li>
            </ul>
          </Card>
          <Card className="p-6 border-primary/20">
            <h3 className="text-lg font-bold mb-3">🎯 Model Management</h3>
            <ul className="space-y-2 text-muted-foreground text-sm">
              <li>• Browse 50+ pre-trained models</li>
              <li>• One-click deployment to devices</li>
              <li>• Automatic version updates</li>
              <li>• A/B testing capabilities</li>
            </ul>
          </Card>
        </div>
      </div>
    ),
  },
  {
    id: 7,
    title: "Device Management & Sync",
    subtitle: "Seamless Edge Deployment",
    content: (
      <div className="flex flex-col justify-center h-full space-y-6">
        <Card className="p-6 bg-muted/30 border-primary/20">
          <h3 className="text-xl font-bold mb-4">Electron Desktop Application</h3>
          <p className="text-muted-foreground mb-4">
            Cross-platform desktop app for Windows, macOS, and Linux with full offline support
          </p>
          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 bg-background rounded-lg text-center">
              <Lock className="w-8 h-8 mx-auto mb-2 text-primary" />
              <p className="font-semibold text-sm">Secure Token Auth</p>
            </div>
            <div className="p-4 bg-background rounded-lg text-center">
              <Network className="w-8 h-8 mx-auto mb-2 text-primary" />
              <p className="font-semibold text-sm">Auto Sync</p>
            </div>
            <div className="p-4 bg-background rounded-lg text-center">
              <Server className="w-8 h-8 mx-auto mb-2 text-primary" />
              <p className="font-semibold text-sm">Local Inference</p>
            </div>
          </div>
        </Card>
        <div className="grid grid-cols-2 gap-6">
          <Card className="p-6 border-primary/20">
            <h3 className="text-lg font-bold mb-3">🔧 Device Setup Features</h3>
            <ul className="space-y-2 text-muted-foreground text-sm">
              <li>• Secure device registration with tokens</li>
              <li>• Automatic model download via Ollama</li>
              <li>• Background sync with cloud platform</li>
              <li>• Offline mode for air-gapped networks</li>
            </ul>
          </Card>
          <Card className="p-6 border-primary/20">
            <h3 className="text-lg font-bold mb-3">⚡ Model Playground</h3>
            <ul className="space-y-2 text-muted-foreground text-sm">
              <li>• Test insurance FNOL processing</li>
              <li>• Validate policy comparisons</li>
              <li>• Parse ACORD forms automatically</li>
              <li>• Document Q&A and search</li>
            </ul>
          </Card>
        </div>
      </div>
    ),
  },
  {
    id: 8,
    title: "Security & Compliance",
    subtitle: "Enterprise-Grade Protection",
    content: (
      <div className="grid grid-cols-2 gap-8 h-full">
        <Card className="p-8 bg-primary/5 border-primary/20">
          <Shield className="w-16 h-16 mb-4 text-primary" />
          <h3 className="text-2xl font-bold mb-4">Compliance Ready</h3>
          <ul className="space-y-3 text-muted-foreground">
            <li className="flex items-start">
              <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
              <span>GDPR compliant data processing</span>
            </li>
            <li className="flex items-start">
              <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
              <span>HIPAA-ready for healthcare data</span>
            </li>
            <li className="flex items-start">
              <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
              <span>SOC 2 Type II certified</span>
            </li>
            <li className="flex items-start">
              <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
              <span>ISO 27001 information security</span>
            </li>
          </ul>
        </Card>
        <Card className="p-8 bg-primary/5 border-primary/20">
          <Lock className="w-16 h-16 mb-4 text-primary" />
          <h3 className="text-2xl font-bold mb-4">Data Protection</h3>
          <ul className="space-y-3 text-muted-foreground">
            <li className="flex items-start">
              <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
              <span>End-to-end encryption (AES-256)</span>
            </li>
            <li className="flex items-start">
              <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
              <span>Zero-knowledge architecture</span>
            </li>
            <li className="flex items-start">
              <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
              <span>Token-based device authentication</span>
            </li>
            <li className="flex items-start">
              <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
              <span>Role-based access control (RBAC)</span>
            </li>
          </ul>
        </Card>
        <Card className="p-8 bg-primary/5 border-primary/20">
          <Server className="w-16 h-16 mb-4 text-primary" />
          <h3 className="text-2xl font-bold mb-4">Infrastructure Security</h3>
          <ul className="space-y-3 text-muted-foreground">
            <li className="flex items-start">
              <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
              <span>Air-gapped deployment support</span>
            </li>
            <li className="flex items-start">
              <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
              <span>VPN and private network support</span>
            </li>
            <li className="flex items-start">
              <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
              <span>On-premise installation options</span>
            </li>
          </ul>
        </Card>
        <Card className="p-8 bg-primary/5 border-primary/20">
          <Globe className="w-16 h-16 mb-4 text-primary" />
          <h3 className="text-2xl font-bold mb-4">Audit & Monitoring</h3>
          <ul className="space-y-3 text-muted-foreground">
            <li className="flex items-start">
              <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
              <span>Complete audit trail logging</span>
            </li>
            <li className="flex items-start">
              <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
              <span>Real-time security monitoring</span>
            </li>
            <li className="flex items-start">
              <CheckCircle className="w-5 h-5 mr-2 text-primary mt-1 flex-shrink-0" />
              <span>Automated threat detection</span>
            </li>
          </ul>
        </Card>
      </div>
    ),
  },
  {
    id: 9,
    title: "Market Opportunity",
    subtitle: "$150B AI Infrastructure Market",
    content: (
      <div className="flex flex-col justify-center h-full space-y-8">
        <div className="grid grid-cols-2 gap-8">
          <Card className="p-8 bg-primary/5 border-primary/20">
            <TrendingUp className="w-16 h-16 mb-4 text-primary" />
            <h3 className="text-3xl font-bold mb-2">$150B</h3>
            <p className="text-lg text-muted-foreground">
              Enterprise AI infrastructure market by 2027 (CAGR 42%)
            </p>
          </Card>
          <Card className="p-8 bg-primary/5 border-primary/20">
            <Users className="w-16 h-16 mb-4 text-primary" />
            <h3 className="text-3xl font-bold mb-2">85%</h3>
            <p className="text-lg text-muted-foreground">
              Of Fortune 500 companies adopting AI by 2025
            </p>
          </Card>
        </div>
        <div className="space-y-6">
          <h3 className="text-2xl font-bold text-center">Target Industries</h3>
          <div className="grid grid-cols-5 gap-4">
            {["Insurance", "Healthcare", "Banking", "Legal", "Travel"].map((industry) => (
              <Card key={industry} className="p-4 text-center border-primary/20">
                <p className="font-semibold">{industry}</p>
              </Card>
            ))}
          </div>
          <p className="text-xl text-center text-muted-foreground max-w-3xl mx-auto">
            Industries with strict compliance requirements, high-value use cases, and regulatory pressure for data sovereignty
          </p>
        </div>
      </div>
    ),
  },
  {
    id: 10,
    title: "Customer Use Cases",
    subtitle: "Real-World Applications",
    content: (
      <div className="grid grid-cols-2 gap-6 h-full">
        <Card className="p-6 bg-accent/10 border-accent/20">
          <h3 className="text-xl font-bold mb-3">🏥 Healthcare Provider</h3>
          <p className="text-muted-foreground mb-4">
            <strong>Challenge:</strong> Process 10,000+ patient records daily while maintaining HIPAA compliance
          </p>
          <p className="text-muted-foreground mb-4">
            <strong>Solution:</strong> Deployed on-premise medical coding model with zero data leakage
          </p>
          <p className="text-primary font-semibold">
            Results: 90% faster processing, 100% compliant, $2M annual savings
          </p>
        </Card>
        <Card className="p-6 bg-accent/10 border-accent/20">
          <h3 className="text-xl font-bold mb-3">🏦 Regional Bank</h3>
          <p className="text-muted-foreground mb-4">
            <strong>Challenge:</strong> Analyze loan applications without sending customer data to cloud APIs
          </p>
          <p className="text-muted-foreground mb-4">
            <strong>Solution:</strong> Private AI tenant with specialized banking models for credit risk assessment
          </p>
          <p className="text-primary font-semibold">
            Results: 75% reduction in processing time, improved loan approval accuracy by 40%
          </p>
        </Card>
        <Card className="p-6 bg-accent/10 border-accent/20">
          <h3 className="text-xl font-bold mb-3">📋 Insurance Company</h3>
          <p className="text-muted-foreground mb-4">
            <strong>Challenge:</strong> Auto-process ACORD forms and FNOL claims at scale
          </p>
          <p className="text-muted-foreground mb-4">
            <strong>Solution:</strong> Domain-specific insurance models deployed across 50+ branch offices
          </p>
          <p className="text-primary font-semibold">
            Results: 60% faster claims processing, 95% accuracy in form extraction
          </p>
        </Card>
        <Card className="p-6 bg-accent/10 border-accent/20">
          <h3 className="text-xl font-bold mb-3">⚖️ Law Firm</h3>
          <p className="text-muted-foreground mb-4">
            <strong>Challenge:</strong> Analyze sensitive legal documents with client confidentiality requirements
          </p>
          <p className="text-muted-foreground mb-4">
            <strong>Solution:</strong> Air-gapped deployment with legal document analysis models
          </p>
          <p className="text-primary font-semibold">
            Results: 80% reduction in document review time, maintained client privilege
          </p>
        </Card>
      </div>
    ),
  },
  {
    id: 11,
    title: "Competitive Advantage",
    subtitle: "Why Fideon Wins",
    content: (
      <div className="grid grid-cols-2 gap-6 h-full">
        <Card className="p-6 bg-primary/5 border-primary/20">
          <h3 className="text-xl font-bold mb-4">🎯 Domain Specialization</h3>
          <p className="text-muted-foreground">
            Pre-trained models for specific industries versus generic AI platforms requiring extensive fine-tuning (saving 6-12 months)
          </p>
        </Card>
        <Card className="p-6 bg-primary/5 border-primary/20">
          <h3 className="text-xl font-bold mb-4">🔒 True Data Sovereignty</h3>
          <p className="text-muted-foreground">
            On-premise deployment with private tenant architecture ensures compliance with GDPR, HIPAA, and other regulations
          </p>
        </Card>
        <Card className="p-6 bg-primary/5 border-primary/20">
          <h3 className="text-xl font-bold mb-4">⚡ Hybrid Architecture</h3>
          <p className="text-muted-foreground">
            Seamless switching between cloud and edge deployment based on workload and security requirements without code changes
          </p>
        </Card>
        <Card className="p-6 bg-primary/5 border-primary/20">
          <h3 className="text-xl font-bold mb-4">🚀 Rapid Deployment</h3>
          <p className="text-muted-foreground">
            One-click model activation and automatic device provisioning versus months of custom integration (3-6 month advantage)
          </p>
        </Card>
        <Card className="p-6 bg-primary/5 border-primary/20">
          <h3 className="text-xl font-bold mb-4">💰 Cost Efficiency</h3>
          <p className="text-muted-foreground">
            Predictable pricing model with local inference reducing API costs by up to 90% ($100K+ annual savings per enterprise)
          </p>
        </Card>
        <Card className="p-6 bg-primary/5 border-primary/20">
          <h3 className="text-xl font-bold mb-4">🔧 Simple Management</h3>
          <p className="text-muted-foreground">
            Unified dashboard for all AI infrastructure versus managing multiple vendor platforms (reduces DevOps overhead by 70%)
          </p>
        </Card>
      </div>
    ),
  },
  {
    id: 12,
    title: "Go-to-Market Strategy",
    subtitle: "Path to Market Leadership",
    content: (
      <div className="flex flex-col justify-center h-full space-y-8">
        <div className="grid grid-cols-3 gap-6">
          <Card className="p-6 border-primary/20 text-center bg-primary/5">
            <Target className="w-12 h-12 mx-auto mb-3 text-primary" />
            <h3 className="text-lg font-bold mb-3">Phase 1: Q1–Q2 2025</h3>
            <p className="text-sm font-semibold text-primary mb-3">Pilot Deployments ✓</p>
            <ul className="text-sm text-muted-foreground text-left space-y-1">
              <li>• <strong>10 enterprise pilots deployed by Q2</strong></li>
              <li>• Current 19-person team handles all pilots</li>
              <li>• Insurance vertical — carriers & MGAs</li>
              <li>• On-site + cloud hybrid setups validated</li>
            </ul>
          </Card>
          <Card className="p-6 border-primary/20 text-center">
            <Rocket className="w-12 h-12 mx-auto mb-3 text-primary" />
            <h3 className="text-lg font-bold mb-3">Phase 2: Q3–Q4 2025</h3>
            <p className="text-sm text-muted-foreground mb-3">Pilot → Production + Expansion</p>
            <ul className="text-sm text-muted-foreground text-left space-y-1">
              <li>• Convert pilots to paid contracts</li>
              <li>• Expand to healthcare and banking</li>
              <li>• Channel partnerships with SIs</li>
              <li>• Scale to 50+ enterprise customers</li>
            </ul>
          </Card>
          <Card className="p-6 border-primary/20 text-center">
            <Globe className="w-12 h-12 mx-auto mb-3 text-primary" />
            <h3 className="text-lg font-bold mb-3">Phase 3: 2026</h3>
            <p className="text-sm text-muted-foreground mb-3">Global Scale</p>
            <ul className="text-sm text-muted-foreground text-left space-y-1">
              <li>• International expansion (EU, APAC)</li>
              <li>• Marketplace for custom models</li>
              <li>• 1,000+ enterprise customers</li>
            </ul>
          </Card>
        </div>
        <div className="grid grid-cols-2 gap-6">
          <Card className="p-6 bg-accent/10 border-accent/20">
            <h3 className="text-lg font-bold mb-3">Sales Channels</h3>
            <ul className="space-y-2 text-muted-foreground text-sm">
              <li>• Direct enterprise sales team (20+ reps by end of year)</li>
              <li>• Strategic partnerships with consultancies (Deloitte, PWC, Accenture)</li>
              <li>• Technology alliances with cloud providers (AWS, Azure, GCP)</li>
              <li>• Industry-specific resellers and VARs</li>
            </ul>
          </Card>
          <Card className="p-6 bg-accent/10 border-accent/20">
            <h3 className="text-lg font-bold mb-3">Marketing Strategy</h3>
            <ul className="space-y-2 text-muted-foreground text-sm">
              <li>• Thought leadership at industry conferences</li>
              <li>• Case studies and ROI calculators</li>
              <li>• Technical content marketing (whitepapers, webinars)</li>
              <li>• Analyst relations (Gartner, Forrester)</li>
            </ul>
          </Card>
        </div>
      </div>
    ),
  },
  {
    id: 13,
    title: "Business Model",
    subtitle: "Multiple Revenue Streams",
    content: (
      <div className="flex flex-col justify-center h-full space-y-8">
        <div className="grid grid-cols-3 gap-6">
          <Card className="p-6 border-primary/20 text-center">
            <h3 className="text-xl font-bold mb-3">Subscription Tiers</h3>
            <div className="space-y-3 text-muted-foreground">
              <div>
                <p className="font-semibold">Starter</p>
                <p className="text-sm">$499/month</p>
                <p className="text-xs">5 devices, 10 models</p>
              </div>
              <div>
                <p className="font-semibold">Professional</p>
                <p className="text-sm">$1,999/month</p>
                <p className="text-xs">25 devices, 50 models</p>
              </div>
              <div>
                <p className="font-semibold">Enterprise</p>
                <p className="text-sm">Custom pricing</p>
                <p className="text-xs">Unlimited devices & models</p>
              </div>
            </div>
          </Card>
          <Card className="p-6 border-primary/20 text-center">
            <h3 className="text-xl font-bold mb-3">Usage-Based</h3>
            <div className="space-y-3 text-muted-foreground">
              <p>Private cloud inference charges</p>
              <p>Storage fees</p>
              <p>API request volume</p>
              <p>Additional devices ($50/device/mo)</p>
            </div>
          </Card>
          <Card className="p-6 border-primary/20 text-center">
            <h3 className="text-xl font-bold mb-3">Premium Services</h3>
            <div className="space-y-3 text-muted-foreground">
              <p>Custom model training ($50K+)</p>
              <p>Dedicated support (24/7)</p>
              <p>On-premise deployments</p>
              <p>Professional services ($200/hr)</p>
            </div>
          </Card>
        </div>
        <Card className="p-8 bg-primary/5 border-primary/20">
          <h3 className="text-2xl font-bold mb-4 text-center">Revenue Projections</h3>
          <div className="grid grid-cols-3 gap-6 text-center">
            <div>
              <p className="text-3xl font-bold text-primary">$3M</p>
              <p className="text-muted-foreground">Year 1 ARR</p>
              <p className="text-sm text-muted-foreground">25 enterprise customers</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-primary">$18M</p>
              <p className="text-muted-foreground">Year 2 ARR</p>
              <p className="text-sm text-muted-foreground">150 enterprise customers</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-primary">$65M</p>
              <p className="text-muted-foreground">Year 3 ARR</p>
              <p className="text-sm text-muted-foreground">500+ enterprise customers</p>
            </div>
          </div>
        </Card>
      </div>
    ),
  },
  {
    id: 17,
    title: "Development Timeline",
    subtitle: "End-to-End Product Delivery Roadmap",
    content: (
      <div className="flex flex-col justify-center h-full space-y-8">
        <div className="grid grid-cols-4 gap-4">
          {[
            { phase: "Phase 1", duration: "Months 1–3", title: "Foundation", icon: <Cog className="w-8 h-8 text-primary" />, items: ["Core cloud platform & auth", "Database schema & RLS", "Admin dashboard MVP", "Device registration API"] },
            { phase: "Phase 2", duration: "Months 3–5", title: "AI Engine", icon: <Sparkles className="w-8 h-8 text-primary" />, items: ["Model marketplace", "Ollama integration", "Playground interfaces", "Electron desktop app"] },
            { phase: "Phase 3", duration: "Months 5–7", title: "Scale & Polish", icon: <Layers className="w-8 h-8 text-primary" />, items: ["Federated learning", "Workflow automation", "Document processing", "Multi-tenant isolation"] },
            { phase: "Phase 4", duration: "Months 7–9 (Q3)", title: "Enterprise Ready", icon: <Rocket className="w-8 h-8 text-primary" />, items: ["Security audit & SOC2", "Performance optimization", "CI/CD & auto-updates", "GA launch"] },
          ].map((p) => (
            <Card key={p.phase} className="p-5 border-primary/20">
              <div className="flex items-center gap-2 mb-2">{p.icon}<span className="text-xs font-semibold text-primary">{p.phase}</span></div>
              <p className="text-sm font-bold text-muted-foreground mb-1">{p.duration}</p>
              <h3 className="text-lg font-bold mb-3">{p.title}</h3>
              <ul className="space-y-1.5 text-muted-foreground text-sm">
                {p.items.map((item) => (
                  <li key={item} className="flex items-start"><CheckCircle className="w-4 h-4 mr-1.5 text-primary mt-0.5 flex-shrink-0" /><span>{item}</span></li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
        <Card className="p-5 bg-primary/5 border-primary/20 text-center">
          <div className="flex items-center justify-center gap-3">
            <Clock className="w-6 h-6 text-primary" />
            <p className="text-xl font-semibold">Total Time to Production: <span className="text-primary">9 Months (Enterprise Ready by Q3)</span> with current team of 19</p>
          </div>
        </Card>
      </div>
    ),
  },
  {
    id: 15,
    title: "How It Functions",
    subtitle: "End-to-End Product Architecture & Flow",
    content: (
      <div className="flex flex-col justify-center h-full space-y-6">
        <div className="grid grid-cols-5 gap-3 items-center">
          {[
            { icon: <Users className="w-10 h-10 text-primary" />, label: "Admin Portal", desc: "Register devices, allocate models, manage users" },
            { icon: <ArrowRight className="w-6 h-6 text-muted-foreground" />, label: "", desc: "" },
            { icon: <Cloud className="w-10 h-10 text-primary" />, label: "Cloud Platform", desc: "Auth, model registry, sync orchestration, analytics" },
            { icon: <ArrowRight className="w-6 h-6 text-muted-foreground" />, label: "", desc: "" },
            { icon: <MonitorSmartphone className="w-10 h-10 text-primary" />, label: "Edge Devices", desc: "Electron app + Ollama for local AI inference" },
          ].map((item, i) => (
            item.label ? (
              <Card key={i} className="p-4 border-primary/20 text-center h-full flex flex-col justify-center">
                <div className="flex justify-center mb-2">{item.icon}</div>
                <h4 className="font-bold text-sm mb-1">{item.label}</h4>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
              </Card>
            ) : (
              <div key={i} className="flex justify-center">{item.icon}</div>
            )
          ))}
        </div>
        <div className="grid grid-cols-3 gap-4">
          <Card className="p-5 border-primary/20">
            <GitBranch className="w-8 h-8 text-primary mb-2" />
            <h3 className="font-bold mb-2">Model Lifecycle</h3>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>• Discover → Activate → Deploy → Monitor</li>
              <li>• Auto-sync to registered devices</li>
              <li>• Version management & rollback</li>
            </ul>
          </Card>
          <Card className="p-5 border-primary/20">
            <Zap className="w-8 h-8 text-primary mb-2" />
            <h3 className="font-bold mb-2">Inference Pipeline</h3>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>• Online: Cloud API with load balancing</li>
              <li>• Offline: Local Ollama with auto-failover</li>
              <li>• Hybrid: Intelligent routing by policy</li>
            </ul>
          </Card>
          <Card className="p-5 border-primary/20">
            <Shield className="w-8 h-8 text-primary mb-2" />
            <h3 className="font-bold mb-2">Security Layer</h3>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>• Token-based device auth (no passwords)</li>
              <li>• RLS on every database table</li>
              <li>• E2E encryption for all sync traffic</li>
            </ul>
          </Card>
        </div>
        <Card className="p-4 bg-accent/10 border-accent/20 text-center">
          <p className="text-lg font-semibold">Data never leaves the customer's network • Models sync metadata only • Zero-knowledge cloud layer</p>
        </Card>
      </div>
    ),
  },
  {
    id: 16,
    title: "Deployment Capacity",
    subtitle: "What the Current Team Can Handle",
    content: (
      <div className="flex flex-col justify-center h-full space-y-8">
        <div className="grid grid-cols-3 gap-6">
          <Card className="p-6 bg-primary/5 border-primary/20 text-center">
            <Server className="w-12 h-12 mx-auto mb-3 text-primary" />
            <h3 className="text-3xl font-bold text-primary">50–100</h3>
            <p className="font-semibold mb-1">Enterprise Tenants</p>
            <p className="text-sm text-muted-foreground">Concurrent isolated deployments managed by a 10-person team</p>
          </Card>
          <Card className="p-6 bg-primary/5 border-primary/20 text-center">
            <MonitorSmartphone className="w-12 h-12 mx-auto mb-3 text-primary" />
            <h3 className="text-3xl font-bold text-primary">5,000+</h3>
            <p className="font-semibold mb-1">Edge Devices</p>
            <p className="text-sm text-muted-foreground">Registered devices with auto-sync, model distribution & health monitoring</p>
          </Card>
          <Card className="p-6 bg-primary/5 border-primary/20 text-center">
            <Layers className="w-12 h-12 mx-auto mb-3 text-primary" />
            <h3 className="text-3xl font-bold text-primary">2–3 / Quarter</h3>
            <p className="font-semibold mb-1">New Verticals</p>
            <p className="text-sm text-muted-foreground">Domain model packs shipped per quarter (insurance, healthcare, banking…)</p>
          </Card>
        </div>
        <div className="grid grid-cols-2 gap-6">
          <Card className="p-6 border-primary/20">
            <h3 className="text-lg font-bold mb-3">👥 Team Composition (10–12)</h3>
            <div className="grid grid-cols-2 gap-2 text-sm text-muted-foreground">
              <div className="flex items-start"><CheckCircle className="w-4 h-4 mr-1.5 text-primary mt-0.5 flex-shrink-0" /><span>1 CTO / Tech Lead</span></div>
              <div className="flex items-start"><CheckCircle className="w-4 h-4 mr-1.5 text-primary mt-0.5 flex-shrink-0" /><span>1 Product Manager</span></div>
              <div className="flex items-start"><CheckCircle className="w-4 h-4 mr-1.5 text-primary mt-0.5 flex-shrink-0" /><span>2 Frontend (React/TS)</span></div>
              <div className="flex items-start"><CheckCircle className="w-4 h-4 mr-1.5 text-primary mt-0.5 flex-shrink-0" /><span>1 Electron Specialist</span></div>
              <div className="flex items-start"><CheckCircle className="w-4 h-4 mr-1.5 text-primary mt-0.5 flex-shrink-0" /><span>2 Backend / API</span></div>
              <div className="flex items-start"><CheckCircle className="w-4 h-4 mr-1.5 text-primary mt-0.5 flex-shrink-0" /><span>2 ML Engineers</span></div>
              <div className="flex items-start"><CheckCircle className="w-4 h-4 mr-1.5 text-primary mt-0.5 flex-shrink-0" /><span>1 MLOps / DevOps</span></div>
              <div className="flex items-start"><CheckCircle className="w-4 h-4 mr-1.5 text-primary mt-0.5 flex-shrink-0" /><span>1 QA Engineer</span></div>
            </div>
          </Card>
          <Card className="p-6 border-primary/20">
            <h3 className="text-lg font-bold mb-3">📈 Scaling Triggers</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li className="flex items-start"><CheckCircle className="w-4 h-4 mr-1.5 text-primary mt-0.5 flex-shrink-0" /><span>100+ tenants → Add 2 SREs for 24/7 ops</span></li>
              <li className="flex items-start"><CheckCircle className="w-4 h-4 mr-1.5 text-primary mt-0.5 flex-shrink-0" /><span>10K+ devices → Dedicated infra team (3)</span></li>
              <li className="flex items-start"><CheckCircle className="w-4 h-4 mr-1.5 text-primary mt-0.5 flex-shrink-0" /><span>5+ verticals → Domain-specific ML squads</span></li>
              <li className="flex items-start"><CheckCircle className="w-4 h-4 mr-1.5 text-primary mt-0.5 flex-shrink-0" /><span>International → Regional support & compliance</span></li>
            </ul>
          </Card>
        </div>
      </div>
    ),
  },
  {
    id: 17,
    title: "Pod Revenue & Scaling Strategy",
    subtitle: "How Each Pod Drives Platform Growth & Revenue",
    content: (
      <div className="flex flex-col justify-center h-full space-y-6">
        <div className="grid grid-cols-2 gap-4">
          {[
            { pod: "Document Retrieval Pod", revenue: "$15K–$50K/yr", scale: "Per-tenant document volume pricing", icon: "📄", how: "AI-powered search across policy docs, contracts & claims. Charges per GB indexed + query volume. Upsell: OCR add-on for scanned docs." },
            { pod: "Quote Generation Pod", revenue: "$25K–$80K/yr", scale: "Per-quote API pricing model", icon: "💰", how: "Automates insurance/finance quote creation. Revenue per generated quote ($0.50–$2). High-margin recurring from renewal cycles." },
            { pod: "Claims FNOL Pod", revenue: "$20K–$60K/yr", scale: "Per-claim processing fees", icon: "📋", how: "First Notice of Loss intake automation. Charges per processed claim. Reduces carrier intake time by 60%, justifying premium pricing." },
            { pod: "Policy Comparison Pod", revenue: "$10K–$40K/yr", scale: "Per-comparison analysis fees", icon: "⚖️", how: "Side-by-side AI analysis of coverage gaps. Per-comparison fee model. High value for brokers managing portfolio renewals." },
            { pod: "ACORD Parser Pod", revenue: "$15K–$45K/yr", scale: "Per-document parsing volume", icon: "🔍", how: "Extracts structured data from ACORD forms. Per-page parsing fee. Critical for carriers receiving 1000s of submissions/month." },
            { pod: "Custom Workflow Pod", revenue: "$30K–$100K/yr", scale: "Per-execution + seat licensing", icon: "⚡", how: "Multi-step AI agent workflows. Premium pricing for complex automation chains. Highest stickiness — customers build processes around it." },
          ].map((p) => (
            <Card key={p.pod} className="p-4 border-primary/20">
              <div className="flex items-start gap-3">
                <span className="text-2xl">{p.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <h4 className="font-bold text-sm">{p.pod}</h4>
                    <span className="text-xs font-semibold text-primary bg-primary/10 px-2 py-0.5 rounded">{p.revenue}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mb-1">{p.how}</p>
                  <p className="text-xs font-medium text-primary/80">Scale: {p.scale}</p>
                </div>
              </div>
            </Card>
          ))}
        </div>
        <Card className="p-4 bg-primary/5 border-primary/20">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <p className="text-2xl font-bold text-primary">$115K–$375K</p>
              <p className="text-xs text-muted-foreground">Revenue per tenant/year (all pods)</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-primary">6 → 15+ Pods</p>
              <p className="text-xs text-muted-foreground">Roadmap: Healthcare, Banking, Legal</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-primary">85%+ Gross Margin</p>
              <p className="text-xs text-muted-foreground">Software + on-prem inference</p>
            </div>
          </div>
        </Card>
      </div>
    ),
  },
  {
    id: 18,
    title: "Team Structure & Responsibilities",
    subtitle: "What Each Team Delivers Under CTO Leadership",
    content: (
      <div className="flex flex-col justify-center h-full space-y-5">
        {/* CTO Header */}
        <Card className="p-3 bg-primary/10 border-primary/30 text-center">
          <p className="text-lg font-bold">CTO — Overall Technical Vision, Architecture & Delivery</p>
        </Card>
        <div className="grid grid-cols-4 gap-4">
          {/* CIO/CSM Team */}
          <Card className="p-4 border-sky-500/30 bg-sky-500/5">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-sky-500/20 flex items-center justify-center">
                <Users className="w-4 h-4 text-sky-600" />
              </div>
              <h3 className="font-bold text-sm text-sky-700">CIO / CSM</h3>
            </div>
            <p className="text-[11px] text-muted-foreground mb-2 font-medium">Client Implementation & Operations</p>
            <div className="space-y-1.5 text-xs text-muted-foreground">
              <div className="flex items-start gap-1"><span className="text-sky-500 mt-0.5">▸</span><span><strong>Leads (1)</strong> — Deployment coordination, sprint planning</span></div>
              <div className="flex items-start gap-1"><span className="text-sky-500 mt-0.5">▸</span><span><strong>BA (1)</strong> — Requirements gathering, client workflows</span></div>
              <div className="flex items-start gap-1"><span className="text-sky-500 mt-0.5">▸</span><span><strong>Engineers (2)</strong> — On-site deployment, infra provisioning</span></div>
              <div className="flex items-start gap-1"><span className="text-sky-500 mt-0.5">▸</span><span><strong>QA (1)</strong> — UAT, integration testing at client sites</span></div>
              <div className="flex items-start gap-1"><span className="text-sky-500 mt-0.5">▸</span><span><strong>Support Lead (1)</strong> — Escalation path, SLA management</span></div>
              <div className="flex items-start gap-1"><span className="text-sky-500 mt-0.5">▸</span><span><strong>Support L1/L2 (2)</strong> — Ticket triage, device troubleshooting</span></div>
            </div>
          </Card>

          {/* Product Architect Team */}
          <Card className="p-4 border-purple-500/30 bg-purple-500/5">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
                <Layers className="w-4 h-4 text-purple-600" />
              </div>
              <h3 className="font-bold text-sm text-purple-700">Product Manager / Architect</h3>
            </div>
            <p className="text-[11px] text-muted-foreground mb-2 font-medium">Platform Engineering & UX</p>
            <div className="space-y-1.5 text-xs text-muted-foreground">
              <div className="flex items-start gap-1"><span className="text-purple-500 mt-0.5">▸</span><span><strong>Frontend Eng (1)</strong> — React/TS dashboard, playground UIs</span></div>
              <div className="flex items-start gap-1"><span className="text-purple-500 mt-0.5">▸</span><span><strong>Electron Dev (1)</strong> — Desktop app, Ollama integration</span></div>
              <div className="flex items-start gap-1"><span className="text-purple-500 mt-0.5">▸</span><span><strong>Backend/API Dev (1)</strong> — Edge functions, REST APIs, sync engine</span></div>
              <div className="flex items-start gap-1"><span className="text-purple-500 mt-0.5">▸</span><span><strong>UI/UX Engineer (1)</strong> — Design system, workflows, user research</span></div>
            </div>
          </Card>

          {/* ML Architect Team */}
          <Card className="p-4 border-indigo-500/30 bg-indigo-500/5">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center">
                <Brain className="w-4 h-4 text-indigo-600" />
              </div>
              <h3 className="font-bold text-sm text-indigo-700">ML Architect</h3>
            </div>
            <p className="text-[11px] text-muted-foreground mb-2 font-medium">AI Models, Training & Deployment</p>
            <div className="space-y-1.5 text-xs text-muted-foreground">
              <div className="flex items-start gap-1"><span className="text-indigo-500 mt-0.5">▸</span><span><strong>ML Engineer (2)</strong> — LoRA fine-tuning, domain model training, GGUF quantization</span></div>
              <div className="flex items-start gap-1"><span className="text-indigo-500 mt-0.5">▸</span><span><strong>MLOps Engineer (1)</strong> — Model packaging, CI/CD for models, A/B testing pipelines</span></div>
            </div>
          </Card>

          {/* QA Team */}
          <Card className="p-4 border-teal-500/30 bg-teal-500/5">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-lg bg-teal-500/20 flex items-center justify-center">
                <CheckCircle className="w-4 h-4 text-teal-600" />
              </div>
              <h3 className="font-bold text-sm text-teal-700">QA Lead</h3>
            </div>
            <p className="text-[11px] text-muted-foreground mb-2 font-medium">Quality, Security & Compliance</p>
            <div className="space-y-1.5 text-xs text-muted-foreground">
              <div className="flex items-start gap-1"><span className="text-teal-500 mt-0.5">▸</span><span><strong>Platform QA (1)</strong> — E2E testing, cross-browser, Electron</span></div>
              <div className="flex items-start gap-1"><span className="text-teal-500 mt-0.5">▸</span><span>Automated regression suites</span></div>
              <div className="flex items-start gap-1"><span className="text-teal-500 mt-0.5">▸</span><span>Security audit coordination (SOC2)</span></div>
              <div className="flex items-start gap-1"><span className="text-teal-500 mt-0.5">▸</span><span>Performance & load testing</span></div>
            </div>
          </Card>
        </div>
        <Card className="p-3 bg-accent/10 border-accent/20 text-center">
          <p className="text-sm font-semibold">Total Headcount: <span className="text-primary">19 people</span> — CTO (1) + CIO Team (8) + Product Team (4) + ML Team (3) + QA (1) + BA (1) + Support (1)</p>
        </Card>
      </div>
    ),
  },
  {
    id: 19,
    title: "Job Descriptions — ML & Product Departments",
    subtitle: "Structured hiring profiles for Product Team and ML Team roles",
    content: (() => {
      const jdRoles = [
        {
          title: "ML Engineer (LoRA / GGUF)",
          dept: "ML Team",
          headcount: "2 headcount",
          color: "indigo",
          icon: Brain,
          education: [
            "Bachelor's degree in Computer Science, Data Science, Mathematics, or a related field",
            "Master's degree in Computational Linguistics, Data Analytics, or similar will be advantageous",
          ],
          experience: [
            "At least 3 years' experience as a Machine Learning Engineer",
            "Proven track record fine-tuning LLMs (Llama, Mistral, Phi) using LoRA / QLoRA",
            "Hands-on experience quantizing models to GGUF format (4-bit, 8-bit) for edge deployment",
          ],
          skills: [
            "Expert-level Python programming including async patterns, memory profiling, and packaging",
            "Deep proficiency with PyTorch: custom training loops, gradient checkpointing, mixed precision (fp16/bf16)",
            "HuggingFace ecosystem: Transformers, PEFT, Datasets, Evaluate, Accelerate libraries",
            "LoRA / QLoRA fine-tuning: rank selection, target module config, adapter merging, and overfitting prevention",
            "GGUF / GGML quantization via llama.cpp: selecting quantization types (Q4_K_M, Q8_0), perplexity benchmarking",
            "Ollama model manifest authoring: Modelfile syntax, system prompt injection, context window config",
            "Prompt engineering: few-shot, chain-of-thought, RAG-augmented, and structured output (JSON mode) techniques",
            "Evaluation frameworks: BLEU, ROUGE, F1, BERTScore, hallucination detection, and domain-specific rubrics",
            "Domain NLP knowledge: named entity recognition, document classification, information extraction from ACORD forms",
            "Data pipeline tooling: pandas, Polars, DVC for dataset versioning, data augmentation and deduplication strategies",
            "Experiment tracking with MLflow or Weights & Biases: metric logging, artifact management, run comparison",
            "Understanding of differential privacy, gradient noise injection, and federated learning aggregation protocols",
            "Familiarity with GPU hardware: VRAM constraints, batch size tuning, multi-GPU training with DeepSpeed / FSDP",
            "Strong mathematical foundations: linear algebra (SVD, eigendecomposition), probability, Bayesian inference, optimization",
          ],
          responsibilities: [
            "Fine-tune open-source LLMs on domain-specific datasets (insurance, healthcare, legal)",
            "Build and maintain training data pipelines: ingestion, cleaning, augmentation, versioning",
            "Evaluate model quality using BLEU, F1, accuracy, and human evaluation frameworks",
            "Engineer prompt templates and guardrails per insurance / healthcare / legal use cases",
            "Collaborate with MLOps to package and deploy models as Ollama-compatible bundles",
          ],
        },
        {
          title: "MLOps Engineer",
          dept: "ML Team",
          headcount: "1 headcount",
          color: "violet",
          icon: GitBranch,
          education: [
            "Bachelor's degree in Computer Science, Software Engineering, or a related field",
            "Master's degree or certification in ML Systems / DevOps will be advantageous",
          ],
          experience: [
            "At least 3 years' experience in an MLOps or DevOps role supporting ML workloads",
            "Proven experience building CI/CD pipelines for model training and deployment",
            "Experience with GPU profiling, latency benchmarking, and inference optimization",
          ],
          skills: [
            "Expert-level Python: scripting automation, CI scripting, API clients for model registries",
            "Docker: multi-stage builds, GPU-enabled containers (NVIDIA runtime), image optimization for edge devices",
            "Kubernetes: Helm chart authoring, CronJob-based training triggers, resource limits for GPU pods",
            "MLflow: experiment tracking, model registry, artifact storage, REST API integration with training pipelines",
            "DVC: data and model versioning, remote storage (S3/GCS), pipeline stages, cache management",
            "CI/CD: GitHub Actions or GitLab CI for triggered training runs, evaluation gates, and conditional deployments",
            "Ollama model packaging: Modelfile authoring, layer caching, model push/pull from private registries",
            "A/B testing infrastructure: traffic splitting at inference layer, shadow mode evaluation, metric collection",
            "Prometheus + Grafana: exposing inference metrics, building dashboards for latency, throughput, and error rates",
            "Federated learning protocols: FedAvg, secure aggregation, privacy budget management (epsilon/delta)",
            "Shell scripting (Bash): automation of model download, checkpointing, and environment bootstrap tasks",
            "Security: secrets management, container scanning, supply chain integrity for model artifacts",
            "Strong understanding of GPU memory hierarchy, CUDA toolkit basics, and driver compatibility",
          ],
          responsibilities: [
            "Build CI/CD pipelines for automated model training, evaluation, and deployment",
            "Package models as Ollama-compatible bundles with versioned manifests and changelogs",
            "Set up A/B testing infrastructure to compare model versions in production",
            "Monitor inference performance: latency, tokens/sec, memory footprint per device class",
            "Maintain federated learning orchestration: gradient aggregation, privacy noise injection",
          ],
        },
        {
          title: "Product Manager / Architect",
          dept: "Product Team",
          headcount: "1 headcount",
          color: "purple",
          icon: Layers,
          education: [
            "Bachelor's degree in Computer Science, Business, or a related field",
            "MBA or Master's degree in Product Management / UX Design will be advantageous",
          ],
          experience: [
            "At least 5 years' experience as a Product Manager in a SaaS or enterprise software environment",
            "Experience in InsurTech, FinTech, or regulated-industry products preferred",
            "Demonstrated track record of shipping features end-to-end across cross-functional teams",
          ],
          skills: [
            "Agile/Scrum mastery: sprint planning, backlog refinement, velocity tracking, and retrospective facilitation",
            "JIRA advanced: epic/story/task hierarchy, custom workflows, JQL querying, release planning boards",
            "Confluence: technical spec writing, decision logs, API contract documentation, ADR templates",
            "Figma: wireframing, high-fidelity prototyping, component libraries, auto-layout, and dev handoff",
            "User research: interview facilitation, usability testing, affinity mapping, and Jobs-to-be-Done framework",
            "API design fluency: REST conventions, OpenAPI 3.0 spec, webhook design, pagination, and error response standards",
            "Data modeling basics: ER diagrams, normalization, understanding of RLS and multi-tenancy implications",
            "Product analytics: Mixpanel or Amplitude for funnel analysis, retention cohorts, and feature adoption metrics",
            "Enterprise software domain: understanding of B2B SaaS pricing models, SSO/SAML, audit logging requirements",
            "InsurTech knowledge: ACORD standards, FNOL workflows, policy lifecycle, submission intake processes",
            "OKR and roadmap tooling: Productboard or Linear for prioritization scoring and stakeholder communication",
            "AI/ML product literacy: understanding of model capabilities, token limits, latency tradeoffs, and prompt design",
            "Compliance awareness: SOC2 Type II, GDPR, HIPAA requirements affecting product feature design",
          ],
          responsibilities: [
            "Define product roadmap, prioritize features, write detailed specs and acceptance criteria",
            "Own sprint planning, backlog grooming, and cross-team dependency management",
            "Translate enterprise client requirements into user stories and technical briefs",
            "Design UX wireframes and prototype flows; validate with end users",
            "Coordinate go-to-market launches with marketing and sales teams",
          ],
        },
        {
          title: "Frontend Engineer (React / TS)",
          dept: "Product Team",
          headcount: "1 headcount",
          color: "purple",
          icon: MonitorSmartphone,
          education: [
            "Bachelor's degree in Computer Science, Software Engineering, or a related field",
            "Relevant certifications in frontend technologies or UX engineering are advantageous",
          ],
          experience: [
            "At least 3 years' experience as a Frontend Developer with React and TypeScript",
            "Experience building enterprise-grade dashboards and real-time data UIs",
            "Track record of owning design systems and component libraries in production",
          ],
          skills: [
            "React 18: concurrent features, Suspense boundaries, useTransition, and server component awareness",
            "TypeScript: strict mode, generics, discriminated unions, utility types, and module augmentation",
            "Tailwind CSS + shadcn/ui: design token customization, CVA variants, dark mode theming, responsive utilities",
            "Vite: plugin authoring, environment variable handling, build chunking strategy, and HMR optimization",
            "TanStack Query (React Query): query invalidation strategies, optimistic updates, infinite scroll, and prefetching",
            "React Hook Form + Zod: complex multi-step form validation, conditional field logic, and schema inference",
            "Supabase JS SDK: real-time channel subscriptions, auth state management, RLS-aware query patterns",
            "WebSocket / SSE: streaming AI response rendering with token-by-token display and abort controller patterns",
            "State management: Zustand or Jotai for global state; understanding of derived state and selector patterns",
            "Performance: React.memo, useMemo, useCallback, virtualized lists (TanStack Virtual), lazy loading routes",
            "Testing: Vitest for unit tests, React Testing Library for component tests, Playwright for E2E flows",
            "Accessibility: WCAG 2.1 AA compliance, ARIA roles, keyboard navigation, screen reader compatibility",
            "CI/CD integration: GitHub Actions for lint, test, and build pipeline; environment-specific deployments",
            "Browser DevTools: performance profiling, memory leak detection, network waterfall analysis",
          ],
          responsibilities: [
            "Build and maintain the cloud dashboard: device management, model marketplace, admin panels",
            
            "Own the design system (Tailwind + shadcn/ui), accessibility, and performance budgets",
            "Integrate real-time subscriptions, auth flows, and file storage in the UI layer",
            "Write component tests and collaborate on E2E test scripts with the QA team",
          ],
        },
        {
          title: "Electron / Desktop Developer",
          dept: "Product Team",
          headcount: "1 headcount",
          color: "blue",
          icon: Server,
          education: [
            "Bachelor's degree in Computer Science, Software Engineering, or a related field",
            "Certifications in cross-platform desktop development are advantageous",
          ],
          experience: [
            "At least 3 years' experience building cross-platform desktop applications with Electron",
            "Experience integrating local AI runtimes (e.g., Ollama) or similar native tooling",
            "Demonstrated experience with app signing, notarization, and automated release pipelines",
          ],
          skills: [
            "Electron architecture: main/renderer process separation, contextBridge isolation, and preload script patterns",
            "Node.js: child_process for Ollama subprocess management, fs/path for model file handling, native addons",
            "IPC design: structured message schemas, error propagation across process boundaries, and async IPC queues",
            "Ollama HTTP API: /api/generate, /api/chat, streaming response parsing, model pull and status polling",
            "GGUF model management: local model storage layout, manifest parsing, partial download resumption",
            "Offline-first sync: IndexedDB or LevelDB for local state, conflict resolution strategies, delta sync queues",
            "Auto-update: electron-updater integration, staged rollouts, code-signed update packages, rollback support",
            "Cross-platform packaging: NSIS (Windows), DMG/pkg (macOS), AppImage/deb/rpm (Linux), GitHub Releases CI",
            "Code signing & notarization: Apple Developer certificates, Windows EV certificates, Gatekeeper compliance",
            "Security: context isolation enforcement, CSP headers in renderer, blocking remote module loading",
            "TypeScript for Electron: shared type contracts between main and renderer, type-safe IPC channel definitions",
            "Performance: lazy loading heavy modules, memory monitoring of renderer processes, GPU acceleration config",
            "Testing: Spectron or Playwright for Electron E2E, mocking Ollama responses in integration tests",
          ],
          responsibilities: [
            "Architect and develop the Fideon Fabric Electron desktop app (Windows, macOS, Linux)",
            "Integrate Ollama runtime for on-device local AI inference without cloud dependency",
            "Build offline-first sync queue, model download manager, and auto-update pipeline",
            "Implement secure IPC between renderer and main process",
            "Handle app signing, notarization, and distribution via electron-builder",
          ],
        },
        {
          title: "Backend / API Developer",
          dept: "Product Team",
          headcount: "1 headcount",
          color: "green",
          icon: Network,
          education: [
            "Bachelor's degree in Computer Science, Information Systems, or a related field",
            "Master's degree in Distributed Systems or Cloud Architecture is advantageous",
          ],
          experience: [
            "At least 4 years' experience as a Backend or API Developer",
            "Experience designing multi-tenant SaaS backends with robust security controls",
            "Proven experience with PostgreSQL, REST APIs, and serverless functions at scale",
          ],
          skills: [
            "TypeScript / Deno: strict typing, module resolution, Deno Deploy runtime, std library, and permission model",
            "Supabase Edge Functions: Deno-based serverless, environment secrets, CORS handling, and streaming responses",
            "PostgreSQL: advanced query optimization, indexes (GIN, BRIN), JSONB operations, CTEs, and window functions",
            "Row Level Security (RLS): policy design for multi-tenant isolation, helper functions, and security definer patterns",
            "REST API design: OpenAPI 3.0 spec, versioning strategy (URL vs header), idempotency, and rate limiting",
            "Device authentication: JWT token validation, device token lifecycle, token rotation, and revocation patterns",
            "Real-time: Supabase Realtime channels, PostgreSQL LISTEN/NOTIFY, and server-sent events for async job status",
            "Federated learning backend: gradient upload endpoints, round orchestration, aggregation trigger logic",
            "Storage: Supabase Storage bucket policies, signed URLs, multipart upload for large model files",
            "Webhook design: payload signing (HMAC-SHA256), retry queues, idempotency keys, and delivery guarantees",
            "Docker: containerizing Deno services, multi-stage builds, health checks, and docker-compose for local dev",
            "Monitoring: structured logging (JSON), OpenTelemetry tracing, Sentry error capture, and SLA alerting",
            "Security: OWASP API Security Top 10, input sanitization, SQL injection prevention, and secrets rotation",
          ],
          responsibilities: [
            "Design and build REST APIs and Edge Functions for device, model, and workflow management",
            "Implement device check-in, model allocation sync engine, and federated learning orchestration",
            "Set up RLS policies, multi-tenant data isolation, and comprehensive audit logging",
            "Integrate third-party services: AI model APIs, email, webhooks, payment processing",
            "Own API documentation, versioning strategy, and SLA monitoring dashboards",
          ],
        },
      ];

      const colorMap: Record<string, { border: string; bg: string; accent: string; badge: string }> = {
        indigo: { border: "border-indigo-500/30", bg: "bg-indigo-500/5", accent: "text-indigo-700", badge: "bg-indigo-100 text-indigo-800" },
        violet: { border: "border-violet-500/30", bg: "bg-violet-500/5", accent: "text-violet-700", badge: "bg-violet-100 text-violet-800" },
        purple: { border: "border-purple-500/30", bg: "bg-purple-500/5", accent: "text-purple-700", badge: "bg-purple-100 text-purple-800" },
        blue:   { border: "border-blue-500/30",   bg: "bg-blue-500/5",   accent: "text-blue-700",   badge: "bg-blue-100 text-blue-800" },
        green:  { border: "border-green-500/30",  bg: "bg-green-500/5",  accent: "text-green-700",  badge: "bg-green-100 text-green-800" },
      };

      return (
        <div className="grid grid-cols-2 gap-5 h-full overflow-y-auto pb-2">
          {jdRoles.map((role) => {
            const c = colorMap[role.color];
            const Icon = role.icon;
            return (
              <Card key={role.title} className={`p-4 ${c.border} ${c.bg} flex flex-col gap-3`}>
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${c.bg} border ${c.border}`}>
                      <Icon className={`w-4 h-4 ${c.accent}`} />
                    </div>
                    <div>
                      <h3 className={`font-bold text-sm ${c.accent}`}>{role.title}</h3>
                      <div className="flex gap-1.5 mt-0.5">
                        <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${c.badge}`}>{role.dept}</span>
                        <span className="text-[9px] px-1.5 py-0.5 rounded-full font-medium bg-muted text-muted-foreground">{role.headcount}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Education */}
                <div>
                  <div className="flex items-center gap-1 mb-1">
                    <GraduationCap className="w-3 h-3 text-muted-foreground" />
                    <p className="text-[9px] font-bold text-muted-foreground uppercase tracking-wide">Education</p>
                  </div>
                  <ul className="space-y-0.5">
                    {role.education.map((e, i) => (
                      <li key={i} className="text-[9px] text-muted-foreground flex items-start gap-1">
                        <span className={`${c.accent} mt-0.5 shrink-0`}>▸</span><span>{e}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Experience */}
                <div>
                  <div className="flex items-center gap-1 mb-1">
                    <Briefcase className="w-3 h-3 text-muted-foreground" />
                    <p className="text-[9px] font-bold text-muted-foreground uppercase tracking-wide">Experience</p>
                  </div>
                  <ul className="space-y-0.5">
                    {role.experience.map((e, i) => (
                      <li key={i} className="text-[9px] text-muted-foreground flex items-start gap-1">
                        <span className={`${c.accent} mt-0.5 shrink-0`}>▸</span><span>{e}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Skills */}
                <div>
                  <div className="flex items-center gap-1 mb-1">
                    <Wrench className="w-3 h-3 text-muted-foreground" />
                    <p className="text-[9px] font-bold text-muted-foreground uppercase tracking-wide">Required Skills</p>
                  </div>
                  <ul className="space-y-0.5">
                    {role.skills.map((s, i) => (
                      <li key={i} className="text-[9px] text-muted-foreground flex items-start gap-1">
                        <span className={`${c.accent} mt-0.5 shrink-0`}>▸</span><span>{s}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Responsibilities */}
                <div>
                  <div className="flex items-center gap-1 mb-1">
                    <ListChecks className="w-3 h-3 text-muted-foreground" />
                    <p className="text-[9px] font-bold text-muted-foreground uppercase tracking-wide">Key Responsibilities</p>
                  </div>
                  <ul className="space-y-0.5">
                    {role.responsibilities.map((r, i) => (
                      <li key={i} className="text-[9px] text-muted-foreground flex items-start gap-1">
                        <span className={`${c.accent} mt-0.5 shrink-0`}>▸</span><span>{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </Card>
            );
          })}
        </div>
      );
    })(),
  },
  {
    id: 20,
    title: "Sprint Plan — Phase 1: Foundation",
    subtitle: "Sprints 1–6 • Months 1–3 • Product & ML Work Independently, Sync at S3",
    content: (
      <div className="flex flex-col justify-center h-full space-y-4">
        {/* Sync banner */}
        <Card className="p-2 bg-amber-500/10 border-amber-500/30 text-center">
          <p className="text-sm font-semibold text-amber-700">
            🔀 Product & ML teams work <span className="underline">independently</span> in S1–S2, then <span className="text-amber-900 font-bold">sync at Sprint 3</span> to align model specs with platform APIs
          </p>
        </Card>

        <div className="grid grid-cols-3 gap-3">
          {[
            {
              sprint: "Sprint 1–2", weeks: "Weeks 1–4",
              product: ["Supabase project setup, auth flows (email/password)", "Database schema: devices, users, roles, audit_logs", "RLS policies on all tables", "Admin dashboard scaffold with sidebar nav"],
              ml: ["Define model taxonomy & domain categories", "Curate training datasets (insurance vertical first)", "Set up model versioning & GGUF pipeline", "Benchmark base models (Llama, Mistral, Phi)"],
              qa: "Schema review, auth flow testing",
            },
            {
              sprint: "Sprint 3–4", weeks: "Weeks 5–8",
              product: ["Device registration API + token auth", "Device check-in & heartbeat endpoints", "Device list/detail UI with status badges", "Model allocation API (assign models → devices)"],
              ml: ["First LoRA fine-tune: Insurance FNOL model", "ACORD form extraction model training", "Quantize models to GGUF (4-bit, 8-bit)", "Define model manifest format for sync"],
              qa: "API integration tests, model output validation",
              sync: true,
            },
            {
              sprint: "Sprint 5–6", weeks: "Weeks 9–12",
              product: ["RBAC implementation (admin/user roles)", "Audit logging with IP & user-agent tracking", "Settings page: profile, preferences, API keys", "Dashboard analytics: device count, model usage"],
              ml: ["Policy comparison model training", "Document retrieval embeddings pipeline", "Model pack creation (bundle per domain)", "Automated evaluation suite (BLEU, F1, accuracy)"],
              qa: "RBAC permission matrix testing, E2E flows",
            },
          ].map((s) => (
            <Card key={s.sprint} className={`p-3 border-sky-500/30 bg-sky-500/5 ${s.sync ? 'ring-2 ring-amber-500/50' : ''}`}>
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-bold text-xs text-sky-700">{s.sprint}</h4>
                <span className="text-[9px] text-muted-foreground">{s.weeks}</span>
              </div>
              {s.sync && <p className="text-[9px] font-bold text-amber-600 mb-1.5">🔗 SYNC POINT — Teams align on model API contracts</p>}
              <div className="space-y-2">
                <div>
                  <p className="text-[9px] font-bold text-purple-600 mb-0.5">Product Team (4 eng)</p>
                  {s.product.map((item) => (
                    <p key={item} className="text-[9px] text-muted-foreground flex items-start gap-1"><span className="text-purple-400 mt-px">▸</span>{item}</p>
                  ))}
                </div>
                <div>
                  <p className="text-[9px] font-bold text-indigo-600 mb-0.5">ML Team (3 eng)</p>
                  {s.ml.map((item) => (
                    <p key={item} className="text-[9px] text-muted-foreground flex items-start gap-1"><span className="text-indigo-400 mt-px">▸</span>{item}</p>
                  ))}
                </div>
                <p className="text-[8px] text-muted-foreground border-t border-sky-500/20 pt-1"><strong>QA:</strong> {s.qa}</p>
              </div>
            </Card>
          ))}
        </div>

        <Card className="p-2 bg-sky-500/10 border-sky-500/30">
          <div className="flex items-center justify-between text-[10px]">
            <span><strong className="text-sky-600">Exit Criteria:</strong> MVP cloud platform with auth, device onboarding, RBAC, and first 3 trained models ready</span>
            <span className="text-sky-600 font-bold">CIO: Pilot site planning & requirements gathering</span>
          </div>
        </Card>
      </div>
    ),
  },
  {
    id: 21,
    title: "Sprint Plan — Phase 2: AI Engine",
    subtitle: "Sprints 7–10 • Months 3–5 • Teams Converge on Integration",
    content: (
      <div className="flex flex-col justify-center h-full space-y-4">
        <div className="grid grid-cols-2 gap-3">
          {[
            {
              sprint: "Sprint 7–8", weeks: "Weeks 13–16",
              product: ["Model marketplace UI: browse, filter, activate", "Model activation flow with domain selection", "Ollama integration: pull, run, status endpoints", "Device sync engine: model distribution pipeline"],
              ml: ["Publish 5 insurance models to marketplace registry", "Quote generation model fine-tuning", "Claims adjudication model training", "Model serving benchmarks (tokens/sec per device class)"],
              qa: "Marketplace E2E, Ollama happy-path testing",
            },
            {
              sprint: "Sprint 9", weeks: "Weeks 17–18",
              product: ["Playground UI: FNOL intake form + AI response", "ACORD parser playground with file upload", "Policy comparison side-by-side UI", "Generic prompt playground with streaming"],
              ml: ["Submission intake triage model", "Prompt template engineering per playground", "Response quality tuning & guardrails", "Model context window optimization"],
              qa: "Playground output validation, edge-case prompts",
            },
            {
              sprint: "Sprint 10", weeks: "Weeks 19–20",
              product: ["Electron desktop app: shell, auth, device registration", "Local inference via Ollama embedded", "Offline mode with sync queue", "Model download manager with progress UI"],
              ml: ["Package all models as Ollama-compatible GGUF", "Create model manifests with version metadata", "Offline inference validation (no network)", "Memory/GPU profiling per model size"],
              qa: "Electron smoke tests, offline/online toggle",
            },
          ].map((s) => (
            <Card key={s.sprint} className="p-3 border-purple-500/30 bg-purple-500/5">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-bold text-xs text-purple-700">{s.sprint}</h4>
                <span className="text-[9px] text-muted-foreground">{s.weeks}</span>
              </div>
              <div className="space-y-2">
                <div>
                  <p className="text-[9px] font-bold text-purple-600 mb-0.5">Product Team</p>
                  {s.product.map((item) => (
                    <p key={item} className="text-[9px] text-muted-foreground flex items-start gap-1"><span className="text-purple-400 mt-px">▸</span>{item}</p>
                  ))}
                </div>
                <div>
                  <p className="text-[9px] font-bold text-indigo-600 mb-0.5">ML Team</p>
                  {s.ml.map((item) => (
                    <p key={item} className="text-[9px] text-muted-foreground flex items-start gap-1"><span className="text-indigo-400 mt-px">▸</span>{item}</p>
                  ))}
                </div>
                <p className="text-[8px] text-muted-foreground border-t border-purple-500/20 pt-1"><strong>QA:</strong> {s.qa}</p>
              </div>
            </Card>
          ))}
        </div>

        <Card className="p-2 bg-purple-500/10 border-purple-500/30">
          <div className="flex items-center justify-between text-[10px]">
            <span><strong className="text-purple-600">Exit Criteria:</strong> Functional AI playground with 8+ models, Electron desktop app with local inference & offline mode</span>
            <span className="text-purple-600 font-bold">CIO: First 2 pilot deployments started</span>
          </div>
        </Card>
      </div>
    ),
  },
  {
    id: 22,
    title: "Sprint Plan — Phase 3: Scale & Polish",
    subtitle: "Sprints 11–14 • Months 5–7 • Production Hardening",
    content: (
      <div className="flex flex-col justify-center h-full space-y-4">
        <div className="grid grid-cols-2 gap-3">
          {[
            {
              sprint: "Sprint 11–12", weeks: "Weeks 21–24",
              product: ["Federated learning UI: round management, participant tracking", "Gradient upload/download APIs with privacy noise", "Workflow builder: visual node editor (React Flow)", "Workflow execution engine with step results"],
              ml: ["Federated aggregation server (FedAvg, FedProx)", "Differential privacy implementation", "Gradient compression & secure aggregation", "Cross-device model convergence testing"],
              qa: "Federated round E2E, workflow execution testing",
            },
            {
              sprint: "Sprint 13", weeks: "Weeks 25–26",
              product: ["Document upload, storage & retrieval UI", "Quote generation playground with carrier selection", "Submission intake wizard with risk scoring", "Email/notification system for workflow alerts"],
              ml: ["Document embeddings model (RAG pipeline)", "Quote generation fine-tuning per carrier", "Risk scoring model calibration", "Submission triage accuracy improvements"],
              qa: "Document processing accuracy, quote validation",
            },
            {
              sprint: "Sprint 14", weeks: "Weeks 27–28",
              product: ["Multi-tenant isolation: schema-level separation", "Tenant provisioning API & admin UI", "Performance optimization: lazy loading, caching", "Error handling, retry logic, graceful degradation"],
              ml: ["Healthcare domain model pack (3 models)", "Banking domain model pack (3 models)", "Model A/B testing framework", "Automated regression tests for all models"],
              qa: "Tenant isolation verification, load testing",
            },
          ].map((s) => (
            <Card key={s.sprint} className="p-3 border-indigo-500/30 bg-indigo-500/5">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-bold text-xs text-indigo-700">{s.sprint}</h4>
                <span className="text-[9px] text-muted-foreground">{s.weeks}</span>
              </div>
              <div className="space-y-2">
                <div>
                  <p className="text-[9px] font-bold text-purple-600 mb-0.5">Product Team</p>
                  {s.product.map((item) => (
                    <p key={item} className="text-[9px] text-muted-foreground flex items-start gap-1"><span className="text-purple-400 mt-px">▸</span>{item}</p>
                  ))}
                </div>
                <div>
                  <p className="text-[9px] font-bold text-indigo-600 mb-0.5">ML Team</p>
                  {s.ml.map((item) => (
                    <p key={item} className="text-[9px] text-muted-foreground flex items-start gap-1"><span className="text-indigo-400 mt-px">▸</span>{item}</p>
                  ))}
                </div>
                <p className="text-[8px] text-muted-foreground border-t border-indigo-500/20 pt-1"><strong>QA:</strong> {s.qa}</p>
              </div>
            </Card>
          ))}
        </div>

        <Card className="p-2 bg-indigo-500/10 border-indigo-500/30">
          <div className="flex items-center justify-between text-[10px]">
            <span><strong className="text-indigo-600">Exit Criteria:</strong> Production-grade multi-tenant platform with federated learning, workflows, 3 domain verticals</span>
            <span className="text-indigo-600 font-bold">CIO: 10 pilots active, feedback loop running</span>
          </div>
        </Card>
      </div>
    ),
  },
  {
    id: 23,
    title: "Sprint Plan — Phase 4: Enterprise Ready",
    subtitle: "Sprints 15–18 • Months 7–9 (Q3) • GA Launch",
    content: (
      <div className="flex flex-col justify-center h-full space-y-4">
        <div className="grid grid-cols-2 gap-3">
          {[
            {
              sprint: "Sprint 15–16", weeks: "Weeks 29–32",
              product: ["Security hardening: CSP headers, rate limiting, input sanitization", "SOC2 evidence collection automation", "Penetration testing coordination & remediation", "Compliance dashboard: audit trail viewer"],
              ml: ["Model security audit: prompt injection testing", "Output filtering & content safety guardrails", "Model provenance documentation", "Privacy compliance: data lineage tracking"],
              qa: "SOC2 gap analysis, penetration test execution",
            },
            {
              sprint: "Sprint 17", weeks: "Weeks 33–34",
              product: ["CI/CD pipeline: automated builds, tests, deploys", "Auto-update system for Electron app", "Performance optimization: bundle size, API latency", "Monitoring & alerting: Sentry, uptime checks"],
              ml: ["Model CI/CD: automated training → evaluation → deploy", "Performance benchmarks per device class", "Model size optimization (pruning, distillation)", "Automated model quality gates"],
              qa: "CI/CD pipeline validation, performance benchmarks",
            },
            {
              sprint: "Sprint 18", weeks: "Weeks 35–36",
              product: ["GA launch prep: landing page, changelog, release notes", "Onboarding wizard for new tenants", "Documentation: admin guide, API docs, troubleshooting", "Pilot → Production migration tooling"],
              ml: ["Legal domain model pack (3 models)", "Travel domain model pack (3 models)", "Model marketplace: 50+ models published", "Training data pipeline documentation"],
              qa: "Full regression, launch readiness checklist",
            },
          ].map((s) => (
            <Card key={s.sprint} className="p-3 border-teal-500/30 bg-teal-500/5">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-bold text-xs text-teal-700">{s.sprint}</h4>
                <span className="text-[9px] text-muted-foreground">{s.weeks}</span>
              </div>
              <div className="space-y-2">
                <div>
                  <p className="text-[9px] font-bold text-purple-600 mb-0.5">Product Team</p>
                  {s.product.map((item) => (
                    <p key={item} className="text-[9px] text-muted-foreground flex items-start gap-1"><span className="text-purple-400 mt-px">▸</span>{item}</p>
                  ))}
                </div>
                <div>
                  <p className="text-[9px] font-bold text-indigo-600 mb-0.5">ML Team</p>
                  {s.ml.map((item) => (
                    <p key={item} className="text-[9px] text-muted-foreground flex items-start gap-1"><span className="text-indigo-400 mt-px">▸</span>{item}</p>
                  ))}
                </div>
                <p className="text-[8px] text-muted-foreground border-t border-teal-500/20 pt-1"><strong>QA:</strong> {s.qa}</p>
              </div>
            </Card>
          ))}
        </div>

        <Card className="p-2 bg-teal-500/10 border-teal-500/30">
          <div className="flex items-center justify-between text-[10px]">
            <span><strong className="text-teal-600">Exit Criteria:</strong> GA launch — SOC2 compliant, 50+ models, 5 verticals, CI/CD, auto-updates, full documentation</span>
            <span className="text-teal-600 font-bold">CIO: Pilot → Production migration complete</span>
          </div>
        </Card>

        <Card className="p-2 bg-primary/5 border-primary/20 text-center">
          <p className="text-sm font-semibold">
            <Clock className="w-4 h-4 inline mr-1" />
            18 sprints × 2 weeks = <span className="text-primary">9 months to GA</span> — Pilots by Q2, Enterprise Ready by Q3
          </p>
        </Card>
      </div>
    ),
  },
  {
    id: 19,
    title: "The Ask",
    subtitle: "Funding Series A",
    content: (
      <div className="flex flex-col justify-center items-center h-full space-y-12">
        <div className="text-center space-y-6">
          <h2 className="text-6xl font-bold text-primary">$8M Series A</h2>
          <p className="text-2xl text-muted-foreground">24-month runway to achieve profitability</p>
        </div>
        <div className="grid grid-cols-2 gap-8 w-full max-w-4xl">
          <Card className="p-6 border-primary/20">
            <h3 className="text-xl font-bold mb-4">Use of Funds</h3>
            <div className="space-y-3 text-muted-foreground">
              <p>• 45% Engineering & Product Development</p>
              <p>• 30% Sales & Marketing</p>
              <p>• 15% Infrastructure & Operations</p>
              <p>• 10% General & Administrative</p>
            </div>
          </Card>
          <Card className="p-6 border-primary/20">
            <h3 className="text-xl font-bold mb-4">Key Milestones (18 Months)</h3>
            <div className="space-y-3 text-muted-foreground">
              <p>• 150+ enterprise customers</p>
              <p>• 15,000+ active devices</p>
              <p>• 75+ domain-specific models</p>
              <p>• $20M ARR, break-even by month 24</p>
            </div>
          </Card>
        </div>
        <div className="text-center space-y-4">
          <p className="text-xl text-muted-foreground">
            Join us in building the future of private, compliant enterprise AI infrastructure
          </p>
          <div className="flex gap-4 justify-center">
            <Button size="lg" className="text-lg px-8">
              Schedule Meeting
            </Button>
            <Button size="lg" variant="outline" className="text-lg px-8">
              View Demo
            </Button>
          </div>
        </div>
      </div>
    ),
  },
];

export default function PitchDeck() {
  const [currentSlide, setCurrentSlide] = useState(0);

  const nextSlide = () => {
    setCurrentSlide((prev) => (prev + 1) % slides.length);
  };

  const prevSlide = () => {
    setCurrentSlide((prev) => (prev - 1 + slides.length) % slides.length);
  };

  const goToSlide = (index: number) => {
    setCurrentSlide(index);
  };

  const exportJDtoPDF = async () => {
    const { default: jsPDF } = await import("jspdf");
    const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
    const pageW = 210;
    const pageH = 297;
    const marginL = 18;
    const marginR = 18;
    const contentW = pageW - marginL - marginR;

    const jdRoles = [
      {
        title: "ML Engineer (LoRA / GGUF)",
        dept: "ML Team · 2 Headcount",
        accentR: 79, accentG: 70, accentB: 229,
        education: [
          "Bachelor's degree in Computer Science, Data Science, Mathematics, or a related field.",
          "Master's degree in Computational Linguistics, Data Analytics, or similar will be advantageous.",
        ],
        experience: [
          "At least 3 years' experience as a Machine Learning Engineer.",
          "Advanced proficiency with Python, Java, and R code writing.",
          "Extensive knowledge of ML frameworks, libraries, data structures, data modeling, and software architecture.",
          "In-depth knowledge of mathematics, statistics, and algorithms.",
        ],
        skills: [
          "Expert-level Python: async patterns, memory profiling, packaging (setuptools/pyproject.toml)",
          "PyTorch: custom training loops, gradient checkpointing, mixed precision (fp16/bf16), DDP training",
          "HuggingFace ecosystem: Transformers, PEFT, Datasets, Evaluate, Accelerate, and TRL libraries",
          "LoRA / QLoRA: rank selection, target module configuration, adapter merging, and overfitting mitigation",
          "GGUF / GGML via llama.cpp: Q4_K_M / Q8_0 quantization, perplexity benchmarking, and VRAM profiling",
          "Ollama Modelfile authoring: system prompt injection, context window config, layer caching strategy",
          "Prompt engineering: few-shot, chain-of-thought, RAG-augmented, structured JSON output techniques",
          "Evaluation: BLEU, ROUGE, BERTScore, hallucination detection, and domain-specific rubric design",
          "NLP for insurance: ACORD form extraction, NER for policy entities, document classification pipelines",
          "Data tooling: pandas, Polars, DVC for dataset versioning, augmentation and deduplication strategies",
          "Experiment tracking: MLflow or W&B — metric logging, artifact management, run comparison",
          "Federated learning: FedAvg aggregation, differential privacy (epsilon/delta budget), gradient noise injection",
          "GPU hardware: VRAM constraints, batch size tuning, multi-GPU training with DeepSpeed or FSDP",
          "Mathematics: linear algebra (SVD, eigendecomposition), probability theory, Bayesian inference, optimization",
        ],
        responsibilities: [
          "Fine-tune open-source LLMs on domain-specific datasets (insurance, healthcare, legal).",
          "Build and maintain training data pipelines: ingestion, cleaning, augmentation, versioning.",
          "Evaluate model quality using BLEU, F1, accuracy, and human evaluation frameworks.",
          "Engineer prompt templates and guardrails per insurance / healthcare / legal use cases.",
          "Collaborate with MLOps to package and deploy models as Ollama-compatible bundles.",
        ],
      },
      {
        title: "MLOps Engineer",
        dept: "ML Team · 1 Headcount",
        accentR: 124, accentG: 58, accentB: 237,
        education: [
          "Bachelor's degree in Computer Science, Software Engineering, or a related field.",
          "Master's degree or certification in ML Systems / DevOps will be advantageous.",
        ],
        experience: [
          "At least 3 years' experience in an MLOps or DevOps role supporting ML workloads.",
          "Advanced proficiency with Python, Docker, and Kubernetes.",
          "Extensive knowledge of MLflow, DVC, and model versioning strategies.",
          "In-depth knowledge of inference performance tuning (tokens/sec, memory footprint).",
        ],
        skills: [
          "Python: automation scripting, CI scripting, API clients for model registries and storage backends",
          "Docker: GPU-enabled containers (NVIDIA runtime), multi-stage builds, image size optimization for edge",
          "Kubernetes: Helm chart authoring, CronJob-based training triggers, GPU resource limits on pods",
          "MLflow: experiment tracking, model registry, artifact storage, REST API integration with pipelines",
          "DVC: data and model versioning, remote storage (S3/GCS), pipeline stages, cache management",
          "CI/CD: GitHub Actions / GitLab CI for triggered training runs, evaluation gates, conditional deployments",
          "Ollama packaging: Modelfile authoring, layer caching, model push/pull from private registries",
          "A/B testing: traffic splitting at inference layer, shadow mode evaluation, metric collection pipelines",
          "Prometheus + Grafana: inference metrics dashboards for latency, throughput, and error rates",
          "Federated learning: FedAvg, secure aggregation, privacy budget management, round orchestration",
          "Shell/Bash: automation of model download, checkpointing, and environment bootstrap tasks",
          "Security: secrets management (Vault/AWS SSM), container scanning, supply chain integrity for artifacts",
          "GPU knowledge: CUDA toolkit basics, driver compatibility, NVML monitoring for utilization metrics",
        ],
        responsibilities: [
          "Build CI/CD pipelines for automated model training, evaluation, and deployment.",
          "Package models as Ollama-compatible bundles with versioned manifests and changelogs.",
          "Set up A/B testing infrastructure to compare model versions in production.",
          "Monitor inference performance: latency, tokens/sec, memory footprint per device class.",
          "Maintain federated learning orchestration: gradient aggregation, privacy noise injection.",
        ],
      },
      {
        title: "Product Manager / Architect",
        dept: "Product Team · 1 Headcount",
        accentR: 139, accentG: 92, accentB: 246,
        education: [
          "Bachelor's degree in Computer Science, Business, or a related field.",
          "MBA or Master's degree in Product Management / UX Design will be advantageous.",
        ],
        experience: [
          "At least 5 years' experience as a Product Manager in SaaS or enterprise software.",
          "Advanced proficiency with Agile/Scrum, JIRA, and Confluence.",
          "Extensive knowledge of UX principles, Figma prototyping, and user research methods.",
          "In-depth knowledge of API design, data modeling, and technical architecture basics.",
        ],
        skills: [
          "Agile/Scrum: sprint planning, backlog refinement, velocity tracking, and retrospective facilitation",
          "JIRA: epic/story/task hierarchy, custom workflows, JQL querying, release planning boards",
          "Confluence: technical spec writing, decision logs, API contract docs, Architecture Decision Records",
          "Figma: high-fidelity prototyping, component libraries, auto-layout, dev handoff workflows",
          "User research: interview facilitation, usability testing, affinity mapping, Jobs-to-be-Done framework",
          "API design fluency: REST conventions, OpenAPI 3.0 spec, webhook design, pagination standards",
          "Data modeling basics: ER diagrams, normalization, RLS and multi-tenancy design implications",
          "Product analytics: Mixpanel/Amplitude for funnel analysis, retention cohorts, feature adoption metrics",
          "InsurTech domain: ACORD standards, FNOL workflows, policy lifecycle, submission intake processes",
          "AI/ML product literacy: token limits, latency tradeoffs, RAG architecture, prompt design basics",
          "Compliance awareness: SOC2 Type II, GDPR, HIPAA requirements affecting product feature design",
          "OKR and roadmap tooling: Linear or Productboard for prioritization scoring and stakeholder communication",
        ],
        responsibilities: [
          "Define product roadmap, prioritize features, write detailed specs and acceptance criteria.",
          "Own sprint planning, backlog grooming, and cross-team dependency management.",
          "Translate enterprise client requirements into user stories and technical briefs.",
          "Design UX wireframes and prototype flows; validate with end users.",
          "Coordinate go-to-market launches with marketing and sales teams.",
        ],
      },
      {
        title: "Frontend Engineer (React / TypeScript)",
        dept: "Product Team · 1 Headcount",
        accentR: 168, accentG: 85, accentB: 247,
        education: [
          "Bachelor's degree in Computer Science, Software Engineering, or a related field.",
          "Relevant certifications in frontend technologies or UX engineering are advantageous.",
        ],
        experience: [
          "At least 3 years' experience as a Frontend Developer with React and TypeScript.",
          "Advanced proficiency with React 18, TypeScript, Tailwind CSS, and Vite.",
          "Extensive knowledge of React Query, REST/WebSocket APIs, and state management.",
          "In-depth knowledge of accessibility (WCAG), performance budgeting, and browser internals.",
        ],
        skills: [
          "React 18: concurrent features, Suspense, useTransition, and server component awareness",
          "TypeScript: strict mode, generics, discriminated unions, utility types, module augmentation",
          "Tailwind CSS + shadcn/ui: design token customization, CVA variants, dark mode theming",
          "Vite: plugin authoring, environment variables, build chunking strategy, and HMR optimization",
          "TanStack Query: query invalidation, optimistic updates, infinite scroll, and prefetching patterns",
          "React Hook Form + Zod: multi-step form validation, conditional field logic, schema inference",
          "Supabase JS SDK: real-time subscriptions, auth state management, RLS-aware query patterns",
          "WebSocket / SSE: streaming AI response rendering, token-by-token display, abort controller",
          "State management: Zustand / Jotai for global state; derived state and selector patterns",
          "Performance: React.memo, virtualized lists (TanStack Virtual), lazy loading, code splitting",
          "Testing: Vitest for unit tests, React Testing Library for components, Playwright for E2E",
          "Accessibility: WCAG 2.1 AA, ARIA roles, keyboard navigation, screen reader compatibility",
          "Browser DevTools: performance profiling, memory leak detection, network waterfall analysis",
        ],
        responsibilities: [
          "Build and maintain the cloud dashboard: device management, model marketplace, admin panels.",
          
          "Own the design system (Tailwind + shadcn/ui), accessibility, and performance budgets.",
          "Integrate real-time subscriptions, auth flows, and file storage in the UI layer.",
          "Write component tests and collaborate on E2E test scripts with QA.",
        ],
      },
      {
        title: "Electron / Desktop Developer",
        dept: "Product Team · 1 Headcount",
        accentR: 59, accentG: 130, accentB: 246,
        education: [
          "Bachelor's degree in Computer Science, Software Engineering, or a related field.",
          "Certifications in cross-platform desktop development are advantageous.",
        ],
        experience: [
          "At least 3 years' experience building cross-platform desktop apps with Electron.",
          "Advanced proficiency with Electron, Node.js, and IPC (inter-process communication).",
          "Extensive knowledge of Ollama API, GGUF model loading, and local inference patterns.",
          "In-depth knowledge of cross-platform packaging (Windows, macOS, Linux) via electron-builder.",
        ],
        skills: [
          "Electron architecture: main/renderer separation, contextBridge isolation, and preload script patterns",
          "Node.js: child_process for Ollama subprocess management, fs/path for model file handling",
          "IPC design: structured message schemas, error propagation across process boundaries, async IPC queues",
          "Ollama HTTP API: /api/generate, /api/chat, streaming response parsing, model pull and status polling",
          "GGUF model management: local model storage layout, manifest parsing, partial download resumption",
          "Offline-first sync: IndexedDB / LevelDB for local state, conflict resolution, delta sync queues",
          "Auto-update: electron-updater integration, staged rollouts, code-signed packages, rollback support",
          "Cross-platform packaging: NSIS (Win), DMG/pkg (macOS), AppImage/deb/rpm (Linux), GitHub Releases CI",
          "Code signing: Apple Developer certificates, Windows EV certificates, Gatekeeper compliance",
          "Security: context isolation, CSP headers in renderer, blocking remote module loading",
          "TypeScript for Electron: shared types between main/renderer, type-safe IPC channel definitions",
          "Testing: Playwright for Electron E2E, mocking Ollama responses in integration test suites",
        ],
        responsibilities: [
          "Architect and develop the Fideon Fabric Electron desktop app (Windows, macOS, Linux).",
          "Integrate Ollama runtime for on-device local AI inference without cloud dependency.",
          "Build offline-first sync queue, model download manager, and auto-update pipeline.",
          "Implement secure IPC between renderer and main process.",
          "Handle app signing, notarization, and distribution via electron-builder.",
        ],
      },
      {
        title: "Backend / API Developer",
        dept: "Product Team · 1 Headcount",
        accentR: 34, accentG: 197, accentB: 94,
        education: [
          "Bachelor's degree in Computer Science, Information Systems, or a related field.",
          "Master's degree in Distributed Systems or Cloud Architecture is advantageous.",
        ],
        experience: [
          "At least 4 years' experience as a Backend or API Developer.",
          "Advanced proficiency with TypeScript / Deno, PostgreSQL, and Docker.",
          "Extensive knowledge of REST/GraphQL API design, versioning, and documentation.",
          "In-depth knowledge of Row Level Security, multi-tenant data isolation, and audit logging.",
        ],
        skills: [
          "TypeScript / Deno: strict typing, module resolution, Deno Deploy runtime, std library, permission model",
          "Supabase Edge Functions: Deno-based serverless, env secrets, CORS handling, and streaming responses",
          "PostgreSQL: query optimization, GIN/BRIN indexes, JSONB operations, CTEs, and window functions",
          "Row Level Security: policy design for multi-tenant isolation, helper functions, security definer patterns",
          "REST API design: OpenAPI 3.0, versioning strategy (URL vs header), idempotency, rate limiting",
          "Device authentication: JWT token validation, device token lifecycle, token rotation and revocation",
          "Real-time: Supabase Realtime channels, PostgreSQL LISTEN/NOTIFY, SSE for async job status",
          "Federated learning backend: gradient upload endpoints, round orchestration, aggregation trigger logic",
          "Storage: bucket policies, signed URLs, multipart upload for large GGUF model file transfers",
          "Webhook design: HMAC-SHA256 payload signing, retry queues, idempotency keys, delivery guarantees",
          "Docker: containerizing Deno services, multi-stage builds, health checks, docker-compose local dev",
          "Security: OWASP API Top 10, input sanitization, SQL injection prevention, secrets rotation policy",
          "Monitoring: structured JSON logging, OpenTelemetry tracing, Sentry error capture, SLA alerting",
        ],
        responsibilities: [
          "Design and build REST APIs and Edge Functions for device, model, and workflow management.",
          "Implement device check-in, model allocation sync engine, and federated learning orchestration.",
          "Set up RLS policies, multi-tenant data isolation, and comprehensive audit logging.",
          "Integrate third-party services: AI model APIs, email, webhooks, payment processing.",
          "Own API documentation, versioning strategy, and SLA monitoring dashboards.",
        ],
      },
    ];

    const drawPageHeader = (pageNum: number, total: number) => {
      // Top accent bar
      doc.setFillColor(30, 27, 75);
      doc.rect(0, 0, pageW, 14, "F");
      doc.setTextColor(255, 255, 255);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(9);
      doc.text("Fideon Fabric", marginL, 9);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(8);
      doc.text(`Page ${pageNum} of ${total}`, pageW - marginR, 9, { align: "right" });
      // Bottom footer
      doc.setFillColor(240, 240, 255);
      doc.rect(0, pageH - 10, pageW, 10, "F");
      doc.setTextColor(100, 100, 150);
      doc.setFontSize(7.5);
      doc.text("Confidential — ML & Product Department Job Descriptions", pageW / 2, pageH - 3.5, { align: "center" });
    };

    const totalPages = jdRoles.length;

    jdRoles.forEach((role, roleIdx) => {
      if (roleIdx > 0) doc.addPage();
      drawPageHeader(roleIdx + 1, totalPages);

      let y = 22;

      // Role title block
      doc.setFillColor(role.accentR, role.accentG, role.accentB);
      doc.roundedRect(marginL, y, contentW, 14, 3, 3, "F");
      doc.setTextColor(255, 255, 255);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(14);
      doc.text(role.title, marginL + 5, y + 9.5);
      y += 18;

      // Dept badge
      doc.setFillColor(role.accentR, role.accentG, role.accentB, 0.15);
      doc.setDrawColor(role.accentR, role.accentG, role.accentB);
      doc.setLineWidth(0.4);
      doc.roundedRect(marginL, y, 65, 7, 2, 2, "FD");
      doc.setTextColor(role.accentR, role.accentG, role.accentB);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(8);
      doc.text(role.dept, marginL + 4, y + 4.8);
      y += 12;

      const sections = [
        { label: "Education", items: role.education },
        { label: "Experience Required", items: role.experience },
        { label: "Required Skills", items: role.skills },
        { label: "Key Responsibilities", items: role.responsibilities },
      ];

      sections.forEach((sec) => {
        // Section header
        doc.setFillColor(role.accentR, role.accentG, role.accentB);
        doc.rect(marginL, y, contentW, 7, "F");
        doc.setTextColor(255, 255, 255);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(9);
        doc.text(sec.label.toUpperCase(), marginL + 4, y + 5);
        y += 9;

        // Items
        doc.setFont("helvetica", "normal");
        doc.setFontSize(9.5);
        doc.setTextColor(40, 40, 60);
        sec.items.forEach((item) => {
          const lines = doc.splitTextToSize(`•  ${item}`, contentW - 6);
          lines.forEach((line: string) => {
            doc.text(line, marginL + 4, y);
            y += 5.2;
          });
          y += 1;
        });
        y += 4;
      });
    });

    doc.save("Fideon_Fabric_Job_Descriptions.pdf");
    toast.success("Job descriptions exported as PDF — 6 roles");
  };

  const exportToPPTX = async () => {
    if (typeof window === "undefined") return;
    if (!(window as any).PptxGenJS) {
      await new Promise<void>((resolve, reject) => {
        const existing = document.querySelector('script[data-pptxgen="1"]') as HTMLScriptElement | null;
        if (existing) {
          existing.addEventListener("load", () => resolve(), { once: true });
          existing.addEventListener("error", () => reject(new Error("Failed to load PptxGenJS")), { once: true });
          if ((window as any).PptxGenJS) resolve();
          return;
        }
        const script = document.createElement("script");
        script.src = "/vendor/pptxgen.min.js";
        script.async = true;
        script.dataset.pptxgen = "1";
        script.onload = () => resolve();
        script.onerror = () => reject(new Error("Failed to load PptxGenJS"));
        document.body.appendChild(script);
      });
    }
    const pptxgen = (window as any).PptxGenJS;
    if (!pptxgen) {
      toast.error("PPTX export library failed to initialize.");
      return;
    }
    const pptx = new pptxgen();
    pptx.author = "Fideon Fabric";
    pptx.company = "Fideon";
    pptx.title = "Fideon Fabric - Investor Pitch Deck";
    pptx.subject = "Enterprise AI Infrastructure";
    pptx.layout = "LAYOUT_WIDE";

    const COLORS = {
      primary: "0066CC",
      primaryLight: "E6F0FF",
      dark: "1A1A2E",
      darkText: "222222",
      subtitle: "555555",
      muted: "666666",
      accent: "00A86B",
      accentLight: "E6F7F0",
      warning: "CC3333",
      warningLight: "FFF0F0",
      white: "FFFFFF",
      bgGray: "F5F7FA",
    };

    const addHeader = (slide: any, title: string, subtitle: string) => {
      slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: "100%", h: 1.4, fill: { color: COLORS.dark } });
      slide.addText(title, { x: 0.6, y: 0.2, w: "85%", h: 0.7, fontSize: 28, bold: true, color: COLORS.white, fontFace: "Arial" });
      slide.addText(subtitle, { x: 0.6, y: 0.85, w: "85%", h: 0.4, fontSize: 14, color: "AAAACC", fontFace: "Arial" });
      slide.addShape(pptx.ShapeType.rect, { x: 0.6, y: 1.25, w: 1.5, h: 0.06, fill: { color: COLORS.primary } });
    };

    const addFooter = (slide: any, num: number, total: number) => {
      slide.addText(`Fideon Fabric`, { x: 0.5, y: 7.0, w: 4, h: 0.3, fontSize: 8, color: COLORS.muted });
      slide.addText(`${num} / ${total}`, { x: 11.5, y: 7.0, w: 1.5, h: 0.3, fontSize: 8, color: COLORS.muted, align: "right" });
    };

    const addCard = (slide: any, x: number, y: number, w: number, h: number, opts?: { fill?: string; border?: string }) => {
      slide.addShape(pptx.ShapeType.roundRect, {
        x, y, w, h,
        rectRadius: 0.1,
        fill: { color: opts?.fill || COLORS.white },
        shadow: { type: "outer", blur: 6, offset: 2, color: "CCCCCC", opacity: 0.3 },
        line: opts?.border ? { color: opts.border, width: 1 } : undefined,
      });
    };

    const totalSlides = slides.length;

    // Helper to create a styled content slide
    const slideData: Array<{
      title: string;
      subtitle: string;
      build: (slide: any) => void;
    }> = [
      // Slide 1: Title
      {
        title: "", subtitle: "",
        build: (slide) => {
          slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: "100%", h: "100%", fill: { color: COLORS.dark } });
          slide.addShape(pptx.ShapeType.rect, { x: 0, y: 3.2, w: "100%", h: 0.08, fill: { color: COLORS.primary } });
          slide.addText("Fideon Fabric", { x: 1, y: 1.5, w: 11, h: 1.2, fontSize: 44, bold: true, color: COLORS.white, fontFace: "Arial", align: "center" });
          slide.addText("Private AI Tenant Infrastructure for Enterprise", { x: 1, y: 3.5, w: 11, h: 0.8, fontSize: 22, color: "AAAACC", fontFace: "Arial", align: "center" });
          slide.addText("Deploy domain-specific AI models on-premise with complete data sovereignty\nwhile maintaining cloud scalability", { x: 2, y: 4.5, w: 9, h: 1, fontSize: 14, color: COLORS.muted, fontFace: "Arial", align: "center" });
        },
      },
      // Slide 2: The Problem
      {
        title: "The Problem", subtitle: "Enterprise AI Adoption Barriers",
        build: (slide) => {
          const problems = [
            { title: "Data Privacy Concerns", desc: "87% of enterprises can't use cloud AI due to regulatory requirements (GDPR, HIPAA, SOC2)" },
            { title: "Generic Models Fall Short", desc: "General-purpose AI lacks domain expertise for insurance, healthcare, and finance" },
            { title: "High Latency & Costs", desc: "Cloud API calls: $0.01–$0.10/request with unpredictable latency" },
            { title: "Complex Infrastructure", desc: "Local AI deployment requires $200K+ annually in specialized DevOps" },
          ];
          problems.forEach((p, i) => {
            const col = i % 2; const row = Math.floor(i / 2);
            const x = 0.5 + col * 6.2; const y = 1.7 + row * 2.5;
            addCard(slide, x, y, 5.8, 2.2, { fill: COLORS.warningLight, border: "FFCCCC" });
            slide.addText(p.title, { x: x + 0.3, y: y + 0.2, w: 5.2, h: 0.5, fontSize: 16, bold: true, color: COLORS.warning });
            slide.addText(p.desc, { x: x + 0.3, y: y + 0.8, w: 5.2, h: 1.2, fontSize: 12, color: COLORS.darkText, valign: "top" });
          });
        },
      },
      // Slide 3: Our Solution
      {
        title: "Our Solution", subtitle: "Hybrid Private AI Tenant Platform",
        build: (slide) => {
          const solutions = [
            { title: "Cloud Management", desc: "Centralized control plane for model distribution, monitoring, and orchestration" },
            { title: "Private Tenant", desc: "Isolated AI infrastructure running on-premise with complete data sovereignty" },
            { title: "Domain Expertise", desc: "Pre-trained models for insurance, healthcare, banking, legal, and travel" },
          ];
          solutions.forEach((s, i) => {
            const x = 0.5 + i * 4.2;
            addCard(slide, x, 1.7, 3.8, 2.8, { fill: COLORS.primaryLight, border: "99CCFF" });
            slide.addText(s.title, { x: x + 0.3, y: 2.0, w: 3.2, h: 0.5, fontSize: 16, bold: true, color: COLORS.primary, align: "center" });
            slide.addText(s.desc, { x: x + 0.3, y: 2.6, w: 3.2, h: 1.5, fontSize: 12, color: COLORS.darkText, align: "center", valign: "top" });
          });
          addCard(slide, 1.5, 5.0, 10, 1.2, { fill: COLORS.bgGray });
          slide.addText("One platform to discover, deploy, and manage domain-specific AI models\nwith enterprise-grade security and zero data leakage", { x: 2, y: 5.1, w: 9, h: 1, fontSize: 14, color: COLORS.darkText, align: "center" });
        },
      },
      // Slide 4: Architecture
      {
        title: "Private AI Tenant Architecture", subtitle: "Complete Data Sovereignty with Cloud Convenience",
        build: (slide) => {
          [
            { title: "On-Premise Deployment", items: ["100% data sovereignty and compliance", "Zero latency for real-time inference", "Works with air-gapped networks"], x: 0.5 },
            { title: "Cloud Management", items: ["Automatic model updates and patches", "Device health monitoring and alerts", "Usage analytics and cost tracking"], x: 6.7 },
          ].forEach((col) => {
            addCard(slide, col.x, 1.7, 5.8, 3.5, { fill: COLORS.primaryLight, border: "99CCFF" });
            slide.addText(col.title, { x: col.x + 0.3, y: 1.9, w: 5.2, h: 0.5, fontSize: 18, bold: true, color: COLORS.primary });
            col.items.forEach((item, i) => {
              slide.addText(`✓  ${item}`, { x: col.x + 0.3, y: 2.6 + i * 0.5, w: 5.2, h: 0.4, fontSize: 12, color: COLORS.darkText });
            });
          });
          addCard(slide, 2, 5.5, 9, 0.9, { fill: COLORS.accentLight, border: "99DDBB" });
          slide.addText("🔒  Your data stays private. Our platform stays powerful.", { x: 2.5, y: 5.6, w: 8, h: 0.7, fontSize: 16, bold: true, color: COLORS.accent, align: "center" });
        },
      },
      // Slide 5: Key Features
      {
        title: "Key Features", subtitle: "Built for Enterprise Scale",
        build: (slide) => {
          const features = [
            { title: "AI Model Marketplace", desc: "50+ domain-specific models across 5 industries with one-click activation" },
            { title: "Hybrid Deployment", desc: "Cloud or on-premise with automatic synchronization and failover" },
            { title: "Device Management", desc: "Register, monitor, and control AI inference devices with token auth" },
            { title: "Model Playground", desc: "Test and validate models with specialized domain interfaces" },
            { title: "Role-Based Access", desc: "Enterprise auth with granular permissions and multi-user support" },
            { title: "Document Processing", desc: "Upload, analyze documents with AI-powered insights" },
          ];
          features.forEach((f, i) => {
            const col = i % 2; const row = Math.floor(i / 2);
            const x = 0.5 + col * 6.2; const y = 1.7 + row * 1.7;
            addCard(slide, x, y, 5.8, 1.5, { fill: COLORS.white, border: "DDDDEE" });
            slide.addText(f.title, { x: x + 0.3, y: y + 0.15, w: 5.2, h: 0.4, fontSize: 14, bold: true, color: COLORS.primary });
            slide.addText(f.desc, { x: x + 0.3, y: y + 0.6, w: 5.2, h: 0.7, fontSize: 11, color: COLORS.darkText });
          });
        },
      },
      // Slide 6: Dashboard
      {
        title: "Platform Dashboard", subtitle: "Intuitive Management Interface",
        build: (slide) => {
          const metrics = [
            { value: "127", label: "Active Devices" },
            { value: "24", label: "Deployed Models" },
            { value: "1.2M", label: "Inferences/Day" },
          ];
          metrics.forEach((m, i) => {
            const x = 0.5 + i * 4.2;
            addCard(slide, x, 1.7, 3.8, 1.5, { fill: COLORS.primaryLight });
            slide.addText(m.value, { x, y: 1.8, w: 3.8, h: 0.8, fontSize: 32, bold: true, color: COLORS.primary, align: "center" });
            slide.addText(m.label, { x, y: 2.6, w: 3.8, h: 0.4, fontSize: 12, color: COLORS.muted, align: "center" });
          });
          [
            { title: "Real-Time Monitoring", items: ["Device health metrics", "Inference latency tracking", "Resource utilization", "Automated alerting"], x: 0.5 },
            { title: "Model Management", items: ["Browse 50+ models", "One-click deployment", "Auto version updates", "A/B testing"], x: 6.7 },
          ].forEach((col) => {
            addCard(slide, col.x, 3.6, 5.8, 3.0, { fill: COLORS.white, border: "DDDDEE" });
            slide.addText(col.title, { x: col.x + 0.3, y: 3.8, w: 5.2, h: 0.4, fontSize: 14, bold: true, color: COLORS.primary });
            col.items.forEach((item, i) => {
              slide.addText(`•  ${item}`, { x: col.x + 0.3, y: 4.4 + i * 0.45, w: 5.2, h: 0.35, fontSize: 11, color: COLORS.darkText });
            });
          });
        },
      },
      // Slide 7: Device Management
      {
        title: "Device Management & Sync", subtitle: "Seamless Edge Deployment",
        build: (slide) => {
          addCard(slide, 0.5, 1.7, 12, 2.2, { fill: COLORS.bgGray });
          slide.addText("Electron Desktop Application", { x: 0.8, y: 1.8, w: 11, h: 0.5, fontSize: 18, bold: true, color: COLORS.darkText });
          slide.addText("Cross-platform for Windows, macOS, and Linux with full offline support", { x: 0.8, y: 2.3, w: 11, h: 0.4, fontSize: 12, color: COLORS.muted });
          ["Secure Token Auth", "Auto Sync", "Local Inference"].forEach((t, i) => {
            addCard(slide, 1 + i * 3.8, 2.9, 3.2, 0.8, { fill: COLORS.white });
            slide.addText(t, { x: 1 + i * 3.8, y: 2.95, w: 3.2, h: 0.7, fontSize: 12, bold: true, color: COLORS.primary, align: "center" });
          });
          [
            { title: "Device Setup Features", items: ["Secure device registration", "Automatic model download", "Background sync", "Offline mode"], x: 0.5 },
            { title: "Model Playground", items: ["Insurance FNOL processing", "Policy comparisons", "ACORD form parsing", "Document Q&A"], x: 6.7 },
          ].forEach((col) => {
            addCard(slide, col.x, 4.2, 5.8, 2.8, { fill: COLORS.white, border: "DDDDEE" });
            slide.addText(col.title, { x: col.x + 0.3, y: 4.4, w: 5.2, h: 0.4, fontSize: 14, bold: true, color: COLORS.primary });
            col.items.forEach((item, i) => {
              slide.addText(`•  ${item}`, { x: col.x + 0.3, y: 5.0 + i * 0.45, w: 5.2, h: 0.35, fontSize: 11, color: COLORS.darkText });
            });
          });
        },
      },
      // Slide 8: Security
      {
        title: "Security & Compliance", subtitle: "Enterprise-Grade Protection",
        build: (slide) => {
          const sections = [
            { title: "Compliance Ready", items: ["GDPR compliant", "HIPAA-ready", "SOC 2 Type II", "ISO 27001"] },
            { title: "Data Protection", items: ["AES-256 encryption", "Zero-knowledge", "Token-based auth", "RBAC"] },
            { title: "Infrastructure", items: ["Air-gapped deploy", "VPN support", "On-premise options"] },
            { title: "Audit & Monitoring", items: ["Full audit trail", "Real-time monitoring", "Threat detection"] },
          ];
          sections.forEach((s, i) => {
            const col = i % 2; const row = Math.floor(i / 2);
            const x = 0.5 + col * 6.2; const y = 1.7 + row * 2.6;
            addCard(slide, x, y, 5.8, 2.3, { fill: COLORS.primaryLight, border: "99CCFF" });
            slide.addText(s.title, { x: x + 0.3, y: y + 0.2, w: 5.2, h: 0.4, fontSize: 16, bold: true, color: COLORS.primary });
            s.items.forEach((item, j) => {
              slide.addText(`✓  ${item}`, { x: x + 0.3, y: y + 0.75 + j * 0.4, w: 5.2, h: 0.35, fontSize: 11, color: COLORS.darkText });
            });
          });
        },
      },
      // Slide 9: Market Opportunity
      {
        title: "Market Opportunity", subtitle: "$150B AI Infrastructure Market",
        build: (slide) => {
          addCard(slide, 0.5, 1.7, 5.8, 2.0, { fill: COLORS.primaryLight });
          slide.addText("$150B", { x: 0.5, y: 1.8, w: 5.8, h: 0.8, fontSize: 36, bold: true, color: COLORS.primary, align: "center" });
          slide.addText("Enterprise AI market by 2027 (42% CAGR)", { x: 0.5, y: 2.6, w: 5.8, h: 0.6, fontSize: 12, color: COLORS.muted, align: "center" });
          addCard(slide, 6.7, 1.7, 5.8, 2.0, { fill: COLORS.primaryLight });
          slide.addText("85%", { x: 6.7, y: 1.8, w: 5.8, h: 0.8, fontSize: 36, bold: true, color: COLORS.primary, align: "center" });
          slide.addText("Fortune 500 adopting AI by 2025", { x: 6.7, y: 2.6, w: 5.8, h: 0.6, fontSize: 12, color: COLORS.muted, align: "center" });
          slide.addText("Target Industries", { x: 0.5, y: 4.2, w: 12, h: 0.5, fontSize: 18, bold: true, color: COLORS.darkText, align: "center" });
          ["Insurance", "Healthcare", "Banking", "Legal", "Travel"].forEach((ind, i) => {
            addCard(slide, 0.8 + i * 2.4, 4.9, 2.0, 0.8, { fill: COLORS.white, border: "DDDDEE" });
            slide.addText(ind, { x: 0.8 + i * 2.4, y: 4.95, w: 2.0, h: 0.7, fontSize: 12, bold: true, color: COLORS.primary, align: "center" });
          });
          slide.addText("Industries with strict compliance, high-value use cases, and regulatory pressure for data sovereignty", { x: 1, y: 6.0, w: 11, h: 0.5, fontSize: 12, color: COLORS.muted, align: "center" });
        },
      },
      // Slide 10: Use Cases
      {
        title: "Customer Use Cases", subtitle: "Real-World Applications",
        build: (slide) => {
          const cases = [
            { icon: "🏥", title: "Healthcare Provider", result: "90% faster, $2M savings", desc: "HIPAA-compliant patient record analysis on-premise" },
            { icon: "🏦", title: "Regional Bank", result: "75% faster, 40% more accurate", desc: "Private credit risk assessment without cloud exposure" },
            { icon: "📋", title: "Insurance Company", result: "60% faster, 95% accuracy", desc: "ACORD parsing & FNOL across 50+ branches" },
            { icon: "⚖️", title: "Law Firm", result: "80% faster review", desc: "Air-gapped legal document analysis" },
          ];
          cases.forEach((c, i) => {
            const col = i % 2; const row = Math.floor(i / 2);
            const x = 0.5 + col * 6.2; const y = 1.7 + row * 2.6;
            addCard(slide, x, y, 5.8, 2.3, { fill: COLORS.accentLight, border: "99DDBB" });
            slide.addText(`${c.icon}  ${c.title}`, { x: x + 0.3, y: y + 0.2, w: 5.2, h: 0.4, fontSize: 14, bold: true, color: COLORS.darkText });
            slide.addText(c.desc, { x: x + 0.3, y: y + 0.7, w: 5.2, h: 0.6, fontSize: 11, color: COLORS.muted });
            slide.addText(c.result, { x: x + 0.3, y: y + 1.5, w: 5.2, h: 0.4, fontSize: 13, bold: true, color: COLORS.accent });
          });
        },
      },
      // Slide 11: Competitive Advantage
      {
        title: "Competitive Advantage", subtitle: "Why Fideon Wins",
        build: (slide) => {
          const advantages = [
            { title: "Domain Specialization", desc: "Pre-trained industry models, saving 6–12 months vs. generic AI" },
            { title: "True Data Sovereignty", desc: "On-premise with GDPR, HIPAA compliance built in" },
            { title: "Hybrid Architecture", desc: "Seamless cloud ↔ edge switching without code changes" },
            { title: "Rapid Deployment", desc: "One-click activation, 3–6 month advantage" },
            { title: "Cost Efficiency", desc: "90% less than cloud APIs, $100K+ savings/enterprise" },
            { title: "Simple Management", desc: "Unified dashboard, 70% less DevOps overhead" },
          ];
          advantages.forEach((a, i) => {
            const col = i % 2; const row = Math.floor(i / 2);
            const x = 0.5 + col * 6.2; const y = 1.7 + row * 1.7;
            addCard(slide, x, y, 5.8, 1.5, { fill: COLORS.primaryLight, border: "99CCFF" });
            slide.addText(a.title, { x: x + 0.3, y: y + 0.15, w: 5.2, h: 0.4, fontSize: 14, bold: true, color: COLORS.primary });
            slide.addText(a.desc, { x: x + 0.3, y: y + 0.6, w: 5.2, h: 0.7, fontSize: 11, color: COLORS.darkText });
          });
        },
      },
      // Slide 12: Go-to-Market
      {
        title: "Go-to-Market Strategy", subtitle: "Path to Market Leadership",
        build: (slide) => {
          const phases = [
            { phase: "Phase 1: Q1–Q2", title: "Pilot Deployments ✓", items: ["10 pilots deployed by Q2", "Current team handles all", "Insurance carriers & MGAs", "Hybrid setups validated"] },
            { phase: "Phase 2: Q3–Q4", title: "Pilot → Production", items: ["Convert pilots to paid", "Healthcare & banking", "50+ customers"] },
            { phase: "Phase 3: 2026", title: "Global Scale", items: ["EU & APAC", "Model marketplace", "1,000+ customers"] },
          ];
          phases.forEach((p, i) => {
            const x = 0.5 + i * 4.2;
            addCard(slide, x, 1.7, 3.8, 3.0, { fill: COLORS.primaryLight, border: "99CCFF" });
            slide.addText(p.phase, { x: x + 0.2, y: 1.8, w: 3.4, h: 0.4, fontSize: 12, bold: true, color: COLORS.primary, align: "center" });
            slide.addText(p.title, { x: x + 0.2, y: 2.2, w: 3.4, h: 0.4, fontSize: 14, bold: true, color: COLORS.darkText, align: "center" });
            p.items.forEach((item, j) => {
              slide.addText(`•  ${item}`, { x: x + 0.4, y: 2.8 + j * 0.4, w: 3.2, h: 0.35, fontSize: 11, color: COLORS.darkText });
            });
          });
          [
            { title: "Sales Channels", items: ["Direct enterprise sales", "SI partnerships (Deloitte, PwC)", "Cloud alliances (AWS, Azure)", "Industry resellers"] },
            { title: "Marketing Strategy", items: ["Conference thought leadership", "Case studies & ROI calculators", "Whitepapers & webinars", "Analyst relations (Gartner)"] },
          ].forEach((col, i) => {
            const x = 0.5 + i * 6.2;
            addCard(slide, x, 5.0, 5.8, 2.2, { fill: COLORS.bgGray });
            slide.addText(col.title, { x: x + 0.3, y: 5.1, w: 5.2, h: 0.4, fontSize: 13, bold: true, color: COLORS.primary });
            col.items.forEach((item, j) => {
              slide.addText(`•  ${item}`, { x: x + 0.3, y: 5.6 + j * 0.35, w: 5.2, h: 0.3, fontSize: 10, color: COLORS.darkText });
            });
          });
        },
      },
      // Slide 13: Business Model
      {
        title: "Business Model", subtitle: "Multiple Revenue Streams",
        build: (slide) => {
          const tiers = [
            { title: "Subscription Tiers", items: ["Starter: $499/mo (5 devices)", "Professional: $1,999/mo (25 devices)", "Enterprise: Custom pricing"] },
            { title: "Usage-Based", items: ["Cloud inference charges", "Storage fees", "API request volume", "Add-on devices ($50/dev/mo)"] },
            { title: "Premium Services", items: ["Custom training ($50K+)", "24/7 dedicated support", "On-premise deployment", "Professional services ($200/hr)"] },
          ];
          tiers.forEach((t, i) => {
            const x = 0.5 + i * 4.2;
            addCard(slide, x, 1.7, 3.8, 3.0, { fill: COLORS.white, border: "DDDDEE" });
            slide.addText(t.title, { x: x + 0.2, y: 1.85, w: 3.4, h: 0.4, fontSize: 14, bold: true, color: COLORS.primary, align: "center" });
            t.items.forEach((item, j) => {
              slide.addText(`•  ${item}`, { x: x + 0.3, y: 2.5 + j * 0.4, w: 3.2, h: 0.35, fontSize: 11, color: COLORS.darkText });
            });
          });
          addCard(slide, 0.5, 5.0, 12, 2.0, { fill: COLORS.primaryLight, border: "99CCFF" });
          slide.addText("Revenue Projections", { x: 0.5, y: 5.1, w: 12, h: 0.5, fontSize: 18, bold: true, color: COLORS.primary, align: "center" });
          [
            { value: "$3M", label: "Year 1 ARR", sub: "25 customers" },
            { value: "$18M", label: "Year 2 ARR", sub: "150 customers" },
            { value: "$65M", label: "Year 3 ARR", sub: "500+ customers" },
          ].forEach((m, i) => {
            const x = 1.5 + i * 3.5;
            slide.addText(m.value, { x, y: 5.6, w: 3, h: 0.6, fontSize: 28, bold: true, color: COLORS.primary, align: "center" });
            slide.addText(m.label, { x, y: 6.2, w: 3, h: 0.3, fontSize: 12, color: COLORS.muted, align: "center" });
            slide.addText(m.sub, { x, y: 6.5, w: 3, h: 0.3, fontSize: 10, color: COLORS.muted, align: "center" });
          });
        },
      },
      // Slide 14: Dev Timeline
      {
        title: "Development Timeline", subtitle: "End-to-End Product Delivery Roadmap",
        build: (slide) => {
          const phases = [
            { phase: "Phase 1", duration: "Mo 1–3", title: "Foundation", items: ["Core platform & auth", "Database & RLS", "Admin dashboard", "Device API"] },
            { phase: "Phase 2", duration: "Mo 3–5", title: "AI Engine", items: ["Model marketplace", "Ollama integration", "Playground UIs", "Electron app"] },
            { phase: "Phase 3", duration: "Mo 5–7", title: "Scale & Polish", items: ["Federated learning", "Workflow engine", "Doc processing", "Multi-tenant"] },
            { phase: "Phase 4", duration: "Mo 7–9 (Q3)", title: "Enterprise Ready", items: ["Security audit", "Performance opt.", "CI/CD pipeline", "GA launch"] },
          ];
          phases.forEach((p, i) => {
            const x = 0.4 + i * 3.15;
            addCard(slide, x, 1.7, 2.9, 3.5, { fill: i < 2 ? COLORS.primaryLight : COLORS.bgGray, border: "99CCFF" });
            slide.addText(`${p.phase}  •  ${p.duration}`, { x: x + 0.15, y: 1.8, w: 2.6, h: 0.35, fontSize: 10, bold: true, color: COLORS.primary });
            slide.addText(p.title, { x: x + 0.15, y: 2.2, w: 2.6, h: 0.4, fontSize: 14, bold: true, color: COLORS.darkText });
            p.items.forEach((item, j) => {
              slide.addText(`✓  ${item}`, { x: x + 0.15, y: 2.75 + j * 0.4, w: 2.6, h: 0.35, fontSize: 10, color: COLORS.darkText });
            });
          });
          addCard(slide, 1.5, 5.5, 10, 1.0, { fill: COLORS.primaryLight });
          slide.addText("⏱  Enterprise Ready by Q3 (9 Months) with current team of 19", { x: 1.5, y: 5.6, w: 10, h: 0.8, fontSize: 16, bold: true, color: COLORS.primary, align: "center" });
        },
      },
      // Slide 15: How It Functions
      // Slide 19: Sprint Plan Phase 1 — Full Detail
      {
        title: "Sprint Plan — Phase 1: Foundation", subtitle: "Sprints 1-6 | Months 1-3 | Product & ML Independent, Sync at S3",
        build: (slide) => {
          // Sync banner
          addCard(slide, 0.5, 1.55, 12, 0.45, { fill: "FEF3C7", border: "F59E0B" });
          slide.addText("Product & ML teams work INDEPENDENTLY in S1-S2, then SYNC at Sprint 3 to align model API contracts with platform", { x: 0.7, y: 1.58, w: 11.5, h: 0.4, fontSize: 9, bold: true, color: "92400E", align: "center" });

          const sprints = [
            {
              s: "Sprint 1-2", weeks: "Weeks 1-4",
              product: [
                "Supabase project setup, auth flows (email/password)",
                "Database schema: devices, users, roles, audit_logs",
                "RLS policies on all tables for data isolation",
                "Admin dashboard scaffold with sidebar navigation",
              ],
              ml: [
                "Define model taxonomy & domain categories",
                "Curate training datasets (insurance vertical first)",
                "Set up model versioning & GGUF pipeline",
                "Benchmark base models (Llama, Mistral, Phi)",
              ],
              qa: "Schema review, auth flow testing",
            },
            {
              s: "Sprint 3-4", weeks: "Weeks 5-8", sync: true,
              product: [
                "Device registration API + token-based auth",
                "Device check-in & heartbeat endpoints",
                "Device list/detail UI with status badges",
                "Model allocation API (assign models to devices)",
              ],
              ml: [
                "First LoRA fine-tune: Insurance FNOL model",
                "ACORD form extraction model training",
                "Quantize models to GGUF (4-bit, 8-bit)",
                "Define model manifest format for sync protocol",
              ],
              qa: "API integration tests, model output validation",
            },
            {
              s: "Sprint 5-6", weeks: "Weeks 9-12",
              product: [
                "RBAC implementation (admin/user roles)",
                "Audit logging with IP & user-agent tracking",
                "Settings page: profile, preferences, API keys",
                "Dashboard analytics: device count, model usage",
              ],
              ml: [
                "Policy comparison model training",
                "Document retrieval embeddings pipeline",
                "Model pack creation (bundle per domain)",
                "Automated eval suite (BLEU, F1, accuracy)",
              ],
              qa: "RBAC permission matrix testing, E2E flows",
            },
          ];

          sprints.forEach((sp, i) => {
            const x = 0.4 + i * 4.2;
            const cardH = 4.6;
            addCard(slide, x, 2.1, 3.9, cardH, { fill: COLORS.white, border: sp.sync ? "F59E0B" : "3B82F6" });

            // Sprint header
            slide.addText(sp.s, { x: x + 0.15, y: 2.15, w: 2.0, h: 0.3, fontSize: 11, bold: true, color: "3B82F6" });
            slide.addText(sp.weeks, { x: x + 2.2, y: 2.15, w: 1.5, h: 0.3, fontSize: 8, color: COLORS.muted, align: "right" });
            if (sp.sync) {
              slide.addText(">> SYNC POINT - Teams align on model API contracts", { x: x + 0.15, y: 2.45, w: 3.6, h: 0.22, fontSize: 7, bold: true, color: "D97706" });
            }

            // Product Team
            const prodY = sp.sync ? 2.7 : 2.5;
            slide.addText("PRODUCT TEAM (4 engineers)", { x: x + 0.15, y: prodY, w: 3.6, h: 0.22, fontSize: 8, bold: true, color: "8B5CF6" });
            sp.product.forEach((item, j) => {
              slide.addText(item, { x: x + 0.35, y: prodY + 0.25 + j * 0.22, w: 3.4, h: 0.2, fontSize: 7, color: COLORS.darkText, bullet: { code: "2022" } });
            });

            // ML Team
            const mlY = prodY + 0.25 + sp.product.length * 0.22 + 0.12;
            slide.addText("ML TEAM (3 engineers)", { x: x + 0.15, y: mlY, w: 3.6, h: 0.22, fontSize: 8, bold: true, color: "4F46E5" });
            sp.ml.forEach((item, j) => {
              slide.addText(item, { x: x + 0.35, y: mlY + 0.25 + j * 0.22, w: 3.4, h: 0.2, fontSize: 7, color: COLORS.darkText, bullet: { code: "2022" } });
            });

            // QA
            const qaY = mlY + 0.25 + sp.ml.length * 0.22 + 0.1;
            slide.addText(`QA: ${sp.qa}`, { x: x + 0.15, y: qaY, w: 3.6, h: 0.2, fontSize: 7, italic: true, color: COLORS.muted });
          });

          // Exit criteria
          addCard(slide, 0.5, 6.85, 12, 0.5, { fill: COLORS.primaryLight, border: "99CCFF" });
          slide.addText("EXIT CRITERIA: MVP cloud platform with auth, device onboarding, RBAC, and first 3 trained models ready for deployment", { x: 0.7, y: 6.9, w: 11.5, h: 0.4, fontSize: 9, bold: true, color: COLORS.primary, align: "center" });
        },
      },
      // Slide 20: Sprint Plan Phase 2 — Full Detail
      {
        title: "Sprint Plan — Phase 2: AI Engine", subtitle: "Sprints 7-10 | Months 3-5 | Teams Converge on Integration",
        build: (slide) => {
          const sprints = [
            {
              s: "Sprint 7-8", weeks: "Weeks 13-16",
              product: [
                "Model marketplace UI: browse, filter, activate",
                "Model activation flow with domain selection",
                "Ollama integration: pull, run, status endpoints",
                "Device sync engine: model distribution pipeline",
              ],
              ml: [
                "Publish 5 insurance models to marketplace registry",
                "Quote generation model fine-tuning",
                "Claims adjudication model training",
                "Model serving benchmarks (tokens/sec per device)",
              ],
              qa: "Marketplace E2E, Ollama happy-path testing",
            },
            {
              s: "Sprint 9", weeks: "Weeks 17-18",
              product: [
                "Playground UI: FNOL intake form + AI response",
                "ACORD parser playground with file upload",
                "Policy comparison side-by-side UI",
                "Generic prompt playground with streaming",
              ],
              ml: [
                "Submission intake triage model",
                "Prompt template engineering per playground",
                "Response quality tuning & guardrails",
                "Model context window optimization",
              ],
              qa: "Playground output validation, edge-case prompts",
            },
            {
              s: "Sprint 10", weeks: "Weeks 19-20",
              product: [
                "Electron desktop app: shell, auth, device reg",
                "Local inference via Ollama embedded runtime",
                "Offline mode with sync queue & retry logic",
                "Model download manager with progress UI",
              ],
              ml: [
                "Package all models as Ollama-compatible GGUF",
                "Create model manifests with version metadata",
                "Offline inference validation (no network)",
                "Memory/GPU profiling per model size",
              ],
              qa: "Electron smoke tests, offline/online toggle",
            },
          ];

          sprints.forEach((sp, i) => {
            const x = 0.4 + i * 4.2;
            addCard(slide, x, 1.55, 3.9, 4.8, { fill: COLORS.white, border: "8B5CF6" });

            slide.addText(sp.s, { x: x + 0.15, y: 1.6, w: 2.0, h: 0.3, fontSize: 11, bold: true, color: "8B5CF6" });
            slide.addText(sp.weeks, { x: x + 2.2, y: 1.6, w: 1.5, h: 0.3, fontSize: 8, color: COLORS.muted, align: "right" });

            const prodY = 1.95;
            slide.addText("PRODUCT TEAM", { x: x + 0.15, y: prodY, w: 3.6, h: 0.22, fontSize: 8, bold: true, color: "8B5CF6" });
            sp.product.forEach((item, j) => {
              slide.addText(item, { x: x + 0.35, y: prodY + 0.25 + j * 0.22, w: 3.4, h: 0.2, fontSize: 7, color: COLORS.darkText, bullet: { code: "2022" } });
            });

            const mlY = prodY + 0.25 + sp.product.length * 0.22 + 0.12;
            slide.addText("ML TEAM", { x: x + 0.15, y: mlY, w: 3.6, h: 0.22, fontSize: 8, bold: true, color: "4F46E5" });
            sp.ml.forEach((item, j) => {
              slide.addText(item, { x: x + 0.35, y: mlY + 0.25 + j * 0.22, w: 3.4, h: 0.2, fontSize: 7, color: COLORS.darkText, bullet: { code: "2022" } });
            });

            const qaY = mlY + 0.25 + sp.ml.length * 0.22 + 0.1;
            slide.addText(`QA: ${sp.qa}`, { x: x + 0.15, y: qaY, w: 3.6, h: 0.2, fontSize: 7, italic: true, color: COLORS.muted });
          });

          addCard(slide, 0.5, 6.5, 12, 0.5, { fill: "F3E8FF", border: "C4B5FD" });
          slide.addText("EXIT CRITERIA: Functional AI playground with 8+ models, Electron desktop app with local inference & offline mode", { x: 0.7, y: 6.55, w: 11.5, h: 0.4, fontSize: 9, bold: true, color: "7C3AED", align: "center" });
        },
      },
      // Slide 21: Sprint Plan Phase 3 — Full Detail
      {
        title: "Sprint Plan — Phase 3: Scale & Polish", subtitle: "Sprints 11-14 | Months 5-7 | Production Hardening",
        build: (slide) => {
          const sprints = [
            {
              s: "Sprint 11-12", weeks: "Weeks 21-24",
              product: [
                "Federated learning UI: round mgmt, participants",
                "Gradient upload/download APIs + privacy noise",
                "Workflow builder: visual node editor (React Flow)",
                "Workflow execution engine with step results",
              ],
              ml: [
                "Federated aggregation server (FedAvg, FedProx)",
                "Differential privacy implementation",
                "Gradient compression & secure aggregation",
                "Cross-device model convergence testing",
              ],
              qa: "Federated round E2E, workflow execution testing",
            },
            {
              s: "Sprint 13", weeks: "Weeks 25-26",
              product: [
                "Document upload, storage & retrieval UI",
                "Quote generation playground + carrier selection",
                "Submission intake wizard with risk scoring",
                "Email/notification system for workflow alerts",
              ],
              ml: [
                "Document embeddings model (RAG pipeline)",
                "Quote generation fine-tuning per carrier",
                "Risk scoring model calibration",
                "Submission triage accuracy improvements",
              ],
              qa: "Document processing accuracy, quote validation",
            },
            {
              s: "Sprint 14", weeks: "Weeks 27-28",
              product: [
                "Multi-tenant isolation: schema-level separation",
                "Tenant provisioning API & admin UI",
                "Performance: lazy loading, caching, pagination",
                "Error handling, retry logic, graceful degradation",
              ],
              ml: [
                "Healthcare domain model pack (3 models)",
                "Banking domain model pack (3 models)",
                "Model A/B testing framework",
                "Automated regression tests for all models",
              ],
              qa: "Tenant isolation verification, load testing",
            },
          ];

          sprints.forEach((sp, i) => {
            const x = 0.4 + i * 4.2;
            addCard(slide, x, 1.55, 3.9, 4.8, { fill: COLORS.white, border: "4F46E5" });

            slide.addText(sp.s, { x: x + 0.15, y: 1.6, w: 2.0, h: 0.3, fontSize: 11, bold: true, color: "4F46E5" });
            slide.addText(sp.weeks, { x: x + 2.2, y: 1.6, w: 1.5, h: 0.3, fontSize: 8, color: COLORS.muted, align: "right" });

            const prodY = 1.95;
            slide.addText("PRODUCT TEAM", { x: x + 0.15, y: prodY, w: 3.6, h: 0.22, fontSize: 8, bold: true, color: "8B5CF6" });
            sp.product.forEach((item, j) => {
              slide.addText(item, { x: x + 0.35, y: prodY + 0.25 + j * 0.22, w: 3.4, h: 0.2, fontSize: 7, color: COLORS.darkText, bullet: { code: "2022" } });
            });

            const mlY = prodY + 0.25 + sp.product.length * 0.22 + 0.12;
            slide.addText("ML TEAM", { x: x + 0.15, y: mlY, w: 3.6, h: 0.22, fontSize: 8, bold: true, color: "4F46E5" });
            sp.ml.forEach((item, j) => {
              slide.addText(item, { x: x + 0.35, y: mlY + 0.25 + j * 0.22, w: 3.4, h: 0.2, fontSize: 7, color: COLORS.darkText, bullet: { code: "2022" } });
            });

            const qaY = mlY + 0.25 + sp.ml.length * 0.22 + 0.1;
            slide.addText(`QA: ${sp.qa}`, { x: x + 0.15, y: qaY, w: 3.6, h: 0.2, fontSize: 7, italic: true, color: COLORS.muted });
          });

          addCard(slide, 0.5, 6.5, 12, 0.5, { fill: "E0E7FF", border: "A5B4FC" });
          slide.addText("EXIT CRITERIA: Production-grade multi-tenant platform with federated learning, workflows, 3 domain verticals", { x: 0.7, y: 6.55, w: 11.5, h: 0.4, fontSize: 9, bold: true, color: "4338CA", align: "center" });
        },
      },
      // Slide 22: Sprint Plan Phase 4 — Full Detail
      {
        title: "Sprint Plan — Phase 4: Enterprise Ready", subtitle: "Sprints 15-18 | Months 7-9 (Q3) | GA Launch",
        build: (slide) => {
          const sprints = [
            {
              s: "Sprint 15-16", weeks: "Weeks 29-32",
              product: [
                "Security hardening: CSP headers, rate limiting",
                "SOC2 evidence collection automation",
                "Penetration testing coordination & remediation",
                "Compliance dashboard: audit trail viewer",
              ],
              ml: [
                "Model security audit: prompt injection testing",
                "Output filtering & content safety guardrails",
                "Model provenance documentation",
                "Privacy compliance: data lineage tracking",
              ],
              qa: "SOC2 gap analysis, penetration test execution",
            },
            {
              s: "Sprint 17", weeks: "Weeks 33-34",
              product: [
                "CI/CD pipeline: automated builds, tests, deploys",
                "Auto-update system for Electron desktop app",
                "Performance optimization: bundle size, API latency",
                "Monitoring & alerting: Sentry, uptime checks",
              ],
              ml: [
                "Model CI/CD: auto training > eval > deploy",
                "Performance benchmarks per device class",
                "Model size optimization (pruning, distillation)",
                "Automated model quality gates",
              ],
              qa: "CI/CD pipeline validation, performance benchmarks",
            },
            {
              s: "Sprint 18", weeks: "Weeks 35-36",
              product: [
                "GA launch prep: landing page, changelog, notes",
                "Onboarding wizard for new tenants",
                "Documentation: admin guide, API docs, FAQ",
                "Pilot to Production migration tooling",
              ],
              ml: [
                "Legal domain model pack (3 models)",
                "Travel domain model pack (3 models)",
                "Model marketplace: 50+ models published",
                "Training data pipeline documentation",
              ],
              qa: "Full regression suite, launch readiness checklist",
            },
          ];

          sprints.forEach((sp, i) => {
            const x = 0.4 + i * 4.2;
            addCard(slide, x, 1.55, 3.9, 4.8, { fill: COLORS.white, border: "14B8A6" });

            slide.addText(sp.s, { x: x + 0.15, y: 1.6, w: 2.0, h: 0.3, fontSize: 11, bold: true, color: "14B8A6" });
            slide.addText(sp.weeks, { x: x + 2.2, y: 1.6, w: 1.5, h: 0.3, fontSize: 8, color: COLORS.muted, align: "right" });

            const prodY = 1.95;
            slide.addText("PRODUCT TEAM", { x: x + 0.15, y: prodY, w: 3.6, h: 0.22, fontSize: 8, bold: true, color: "8B5CF6" });
            sp.product.forEach((item, j) => {
              slide.addText(item, { x: x + 0.35, y: prodY + 0.25 + j * 0.22, w: 3.4, h: 0.2, fontSize: 7, color: COLORS.darkText, bullet: { code: "2022" } });
            });

            const mlY = prodY + 0.25 + sp.product.length * 0.22 + 0.12;
            slide.addText("ML TEAM", { x: x + 0.15, y: mlY, w: 3.6, h: 0.22, fontSize: 8, bold: true, color: "4F46E5" });
            sp.ml.forEach((item, j) => {
              slide.addText(item, { x: x + 0.35, y: mlY + 0.25 + j * 0.22, w: 3.4, h: 0.2, fontSize: 7, color: COLORS.darkText, bullet: { code: "2022" } });
            });

            const qaY = mlY + 0.25 + sp.ml.length * 0.22 + 0.1;
            slide.addText(`QA: ${sp.qa}`, { x: x + 0.15, y: qaY, w: 3.6, h: 0.2, fontSize: 7, italic: true, color: COLORS.muted });
          });

          addCard(slide, 0.5, 6.5, 12, 0.5, { fill: "CCFBF1", border: "5EEAD4" });
          slide.addText("EXIT CRITERIA: GA Launch - SOC2 compliant, 50+ models, 5 verticals, CI/CD, auto-updates, full documentation", { x: 0.7, y: 6.55, w: 11.5, h: 0.4, fontSize: 9, bold: true, color: "0F766E", align: "center" });
        },
      },
      {
        title: "How It Functions", subtitle: "End-to-End Architecture & Flow",
        build: (slide) => {
          ["Admin Portal", "→", "Cloud Platform", "→", "Edge Devices"].forEach((label, i) => {
            const x = 0.5 + i * 2.4;
            if (label === "→") {
              slide.addText("→", { x, y: 2.0, w: 2, h: 0.8, fontSize: 24, color: COLORS.muted, align: "center" });
            } else {
              addCard(slide, x, 1.7, 2.2, 1.2, { fill: COLORS.primaryLight, border: "99CCFF" });
              slide.addText(label, { x, y: 1.85, w: 2.2, h: 0.9, fontSize: 13, bold: true, color: COLORS.primary, align: "center" });
            }
          });
          const cols = [
            { title: "Model Lifecycle", items: ["Discover → Activate → Deploy → Monitor", "Auto-sync to devices", "Version mgmt & rollback"] },
            { title: "Inference Pipeline", items: ["Online: Cloud API + load balancing", "Offline: Local Ollama + failover", "Hybrid: Intelligent routing"] },
            { title: "Security Layer", items: ["Token-based device auth", "RLS on every table", "E2E encryption for sync"] },
          ];
          cols.forEach((c, i) => {
            const x = 0.5 + i * 4.2;
            addCard(slide, x, 3.3, 3.8, 2.5, { fill: COLORS.white, border: "DDDDEE" });
            slide.addText(c.title, { x: x + 0.2, y: 3.4, w: 3.4, h: 0.4, fontSize: 13, bold: true, color: COLORS.primary });
            c.items.forEach((item, j) => {
              slide.addText(`•  ${item}`, { x: x + 0.2, y: 3.9 + j * 0.4, w: 3.4, h: 0.35, fontSize: 10, color: COLORS.darkText });
            });
          });
          addCard(slide, 1.5, 6.1, 10, 0.8, { fill: COLORS.accentLight });
          slide.addText("Data never leaves customer network  •  Models sync metadata only  •  Zero-knowledge cloud", { x: 1.5, y: 6.2, w: 10, h: 0.6, fontSize: 12, bold: true, color: COLORS.accent, align: "center" });
        },
      },
      // Slide 16: Deployment Capacity
      {
        title: "Deployment Capacity", subtitle: "What the Current Team Can Handle",
        build: (slide) => {
          const metrics = [
            { value: "50–100", label: "Enterprise Tenants", desc: "Concurrent isolated deployments" },
            { value: "5,000+", label: "Edge Devices", desc: "Auto-sync & health monitoring" },
            { value: "2–3 / Qtr", label: "New Verticals", desc: "Domain packs per quarter" },
          ];
          metrics.forEach((m, i) => {
            const x = 0.5 + i * 4.2;
            addCard(slide, x, 1.7, 3.8, 2.0, { fill: COLORS.primaryLight });
            slide.addText(m.value, { x, y: 1.8, w: 3.8, h: 0.7, fontSize: 28, bold: true, color: COLORS.primary, align: "center" });
            slide.addText(m.label, { x, y: 2.5, w: 3.8, h: 0.4, fontSize: 13, bold: true, color: COLORS.darkText, align: "center" });
            slide.addText(m.desc, { x, y: 2.9, w: 3.8, h: 0.4, fontSize: 10, color: COLORS.muted, align: "center" });
          });
          [
            { title: "Team (10–12)", items: ["1 CTO / Tech Lead", "1 Product Manager", "2 Frontend (React/TS)", "1 Electron Specialist", "2 Backend/API", "2 ML Engineers", "1 MLOps", "1 QA"] },
            { title: "Scaling Triggers", items: ["100+ tenants → 2 SREs", "10K+ devices → Infra team (3)", "5+ verticals → ML squads", "International → Regional support"] },
          ].forEach((col, i) => {
            const x = 0.5 + i * 6.2;
            addCard(slide, x, 4.0, 5.8, 3.0, { fill: COLORS.bgGray, border: "DDDDEE" });
            slide.addText(col.title, { x: x + 0.3, y: 4.1, w: 5.2, h: 0.4, fontSize: 14, bold: true, color: COLORS.primary });
            col.items.forEach((item, j) => {
              slide.addText(`✓  ${item}`, { x: x + 0.3, y: 4.6 + j * 0.3, w: 5.2, h: 0.25, fontSize: 10, color: COLORS.darkText });
            });
          });
        },
      },
      // Slide 17: Pod Revenue
      {
        title: "Pod Revenue & Scaling Strategy", subtitle: "How Each Pod Drives Growth & Revenue",
        build: (slide) => {
          const pods = [
            { pod: "Document Retrieval", revenue: "$15K–$50K/yr", desc: "Per-GB indexed + query volume pricing" },
            { pod: "Quote Generation", revenue: "$25K–$80K/yr", desc: "Per-quote API pricing ($0.50–$2/quote)" },
            { pod: "Claims FNOL", revenue: "$20K–$60K/yr", desc: "Per-claim processing fees" },
            { pod: "Policy Comparison", revenue: "$10K–$40K/yr", desc: "Per-comparison analysis fees" },
            { pod: "ACORD Parser", revenue: "$15K–$45K/yr", desc: "Per-page parsing volume" },
            { pod: "Custom Workflows", revenue: "$30K–$100K/yr", desc: "Per-execution + seat licensing" },
          ];
          pods.forEach((p, i) => {
            const col = i % 2; const row = Math.floor(i / 2);
            const x = 0.5 + col * 6.2; const y = 1.7 + row * 1.6;
            addCard(slide, x, y, 5.8, 1.4, { fill: COLORS.white, border: "DDDDEE" });
            slide.addText(p.pod, { x: x + 0.3, y: y + 0.1, w: 3.5, h: 0.4, fontSize: 13, bold: true, color: COLORS.darkText });
            slide.addText(p.revenue, { x: x + 3.8, y: y + 0.1, w: 1.7, h: 0.4, fontSize: 11, bold: true, color: COLORS.primary, align: "right" });
            slide.addText(p.desc, { x: x + 0.3, y: y + 0.6, w: 5.2, h: 0.5, fontSize: 10, color: COLORS.muted });
          });
          addCard(slide, 0.5, 6.5, 12, 0.8, { fill: COLORS.primaryLight });
          const summaries = ["$115K–$375K / tenant / year", "6 → 15+ Pods roadmap", "85%+ Gross Margin"];
          summaries.forEach((s, i) => {
            slide.addText(s, { x: 0.8 + i * 4, y: 6.55, w: 3.5, h: 0.7, fontSize: 13, bold: true, color: COLORS.primary, align: "center" });
          });
        },
      },
      // Slide 18: Team Structure
      {
        title: "Team Structure & Responsibilities", subtitle: "What Each Team Delivers Under CTO Leadership",
        build: (slide) => {
          addCard(slide, 0.5, 1.7, 12, 0.7, { fill: COLORS.primaryLight });
          slide.addText("CTO — Overall Technical Vision, Architecture & Delivery", { x: 0.5, y: 1.75, w: 12, h: 0.6, fontSize: 14, bold: true, color: COLORS.primary, align: "center" });

          const teams = [
            { title: "CIO / CSM", subtitle: "Client Implementation & Ops", color: "3B82F6", items: ["Leads (1) — Deploy coordination", "BA (1) — Requirements & workflows", "Engineers (2) — Infra provisioning", "QA (1) — UAT & integration", "Support Lead (1) — SLA mgmt", "Support L1/L2 (2) — Triage"] },
            { title: "Product Architect", subtitle: "Platform Engineering & UX", color: "8B5CF6", items: ["Frontend (1) — React dashboard", "Electron Dev (1) — Desktop app", "Backend/API (1) — Edge functions", "UI/UX (1) — Design system"] },
            { title: "ML Architect", subtitle: "AI Models & Training", color: "4F46E5", items: ["ML Engineer (2) — LoRA fine-tuning", "MLOps (1) — Model CI/CD", "GGUF quantization & packaging", "A/B testing pipelines"] },
            { title: "QA Lead", subtitle: "Quality & Compliance", color: "14B8A6", items: ["Platform QA (1) — E2E testing", "Automated regression suites", "SOC2 security audit coord.", "Performance & load testing"] },
          ];
          teams.forEach((t, i) => {
            const x = 0.4 + i * 3.15;
            addCard(slide, x, 2.6, 2.9, 4.0, { fill: COLORS.white, border: t.color });
            slide.addText(t.title, { x: x + 0.15, y: 2.7, w: 2.6, h: 0.4, fontSize: 13, bold: true, color: t.color });
            slide.addText(t.subtitle, { x: x + 0.15, y: 3.1, w: 2.6, h: 0.3, fontSize: 9, color: COLORS.muted });
            t.items.forEach((item, j) => {
              slide.addText(`▸  ${item}`, { x: x + 0.15, y: 3.5 + j * 0.35, w: 2.6, h: 0.3, fontSize: 9, color: COLORS.darkText });
            });
          });
          addCard(slide, 1.5, 6.8, 10, 0.6, { fill: COLORS.accentLight });
          slide.addText("Total Headcount: 19 people — CTO (1) + CIO Team (8) + Product (4) + ML (3) + QA (1) + BA (1) + Support (1)", { x: 1.5, y: 6.85, w: 10, h: 0.5, fontSize: 11, bold: true, color: COLORS.accent, align: "center" });
        },
      },
      // Slides 19–24: Individual Job Descriptions (ML & Product) — one per role
      ...([
        {
          title: "Job Description — ML Engineer (LoRA / GGUF)",
          dept: "ML Team · 2 Headcount",
          color: "4F46E5",
          education: [
            "Bachelor's degree in Computer Science, Data Science, Mathematics, or a related field.",
            "Master's degree in Computational Linguistics, Data Analytics, or similar will be advantageous.",
          ],
          experience: [
            "At least 3 years' experience as a Machine Learning Engineer.",
            "Proven track record fine-tuning LLMs (Llama, Mistral, Phi) using LoRA / QLoRA.",
            "Hands-on experience quantizing models to GGUF format (4-bit, 8-bit) for edge deployment.",
          ],
          skills: [
            "Advanced proficiency with Python; familiarity with Java or R advantageous.",
            "Extensive knowledge of ML frameworks: PyTorch, HuggingFace Transformers, llama.cpp.",
            "In-depth knowledge of mathematics, statistics, and algorithms.",
            "Superb analytical and problem-solving abilities.",
            "Great communication and collaboration skills across cross-functional teams.",
            "Excellent time management and organizational abilities.",
          ],
          responsibilities: [
            "Fine-tune open-source LLMs on domain-specific datasets (insurance, healthcare, legal).",
            "Build and maintain training data pipelines: ingestion, cleaning, augmentation, versioning.",
            "Evaluate model quality using BLEU, F1, accuracy, and human evaluation frameworks.",
            "Engineer prompt templates and guardrails per use case.",
            "Collaborate with MLOps to package and deploy models as Ollama-compatible bundles.",
          ],
        },
        {
          title: "Job Description — MLOps Engineer",
          dept: "ML Team · 1 Headcount",
          color: "7C3AED",
          education: [
            "Bachelor's degree in Computer Science, Software Engineering, or a related field.",
            "Master's degree or certification in ML Systems / DevOps will be advantageous.",
          ],
          experience: [
            "At least 3 years' experience in an MLOps or DevOps role supporting ML workloads.",
            "Proven experience building CI/CD pipelines for model training and deployment.",
            "Experience with GPU profiling, latency benchmarking, and inference optimization.",
          ],
          skills: [
            "Advanced proficiency with Python, Docker, and Kubernetes.",
            "Extensive knowledge of MLflow, DVC, and model versioning strategies.",
            "In-depth knowledge of inference performance tuning (tokens/sec, memory footprint).",
            "Superb analytical and problem-solving abilities in distributed systems.",
            "Great communication skills to surface findings to engineering and product teams.",
            "Excellent organizational abilities to manage concurrent model release pipelines.",
          ],
          responsibilities: [
            "Build CI/CD pipelines for automated model training, evaluation, and deployment.",
            "Package models as Ollama-compatible bundles with versioned manifests and changelogs.",
            "Set up A/B testing infrastructure to compare model versions in production.",
            "Monitor inference performance: latency, tokens/sec, memory footprint per device class.",
            "Maintain federated learning orchestration: gradient aggregation, privacy noise injection.",
          ],
        },
        {
          title: "Job Description — Product Manager / Architect",
          dept: "Product Team · 1 Headcount",
          color: "8B5CF6",
          education: [
            "Bachelor's degree in Computer Science, Business, or a related field.",
            "MBA or Master's degree in Product Management / UX Design will be advantageous.",
          ],
          experience: [
            "At least 5 years' experience as a Product Manager in SaaS or enterprise software.",
            "Experience in InsurTech, FinTech, or regulated-industry products preferred.",
            "Track record of shipping features end-to-end across cross-functional teams.",
          ],
          skills: [
            "Advanced proficiency with Agile/Scrum, JIRA, and Confluence.",
            "Extensive knowledge of UX principles, Figma prototyping, and user research methods.",
            "In-depth knowledge of API design, data modeling, and technical architecture basics.",
            "Superb analytical and problem-solving abilities; data-driven decision making.",
            "Great communication and stakeholder management skills at executive level.",
            "Excellent time management and sprint planning capabilities.",
          ],
          responsibilities: [
            "Define product roadmap, prioritize features, write detailed specs and acceptance criteria.",
            "Own sprint planning, backlog grooming, and cross-team dependency management.",
            "Translate enterprise client requirements into user stories and technical briefs.",
            "Design UX wireframes and prototype flows; validate with end users.",
            "Coordinate go-to-market launches with marketing and sales teams.",
          ],
        },
        {
          title: "Job Description — Frontend Engineer (React / TS)",
          dept: "Product Team · 1 Headcount",
          color: "A855F7",
          education: [
            "Bachelor's degree in Computer Science, Software Engineering, or a related field.",
            "Relevant certifications in frontend technologies or UX engineering are advantageous.",
          ],
          experience: [
            "At least 3 years' experience as a Frontend Developer with React and TypeScript.",
            "Experience building enterprise-grade dashboards and real-time data UIs.",
            "Track record of owning design systems and component libraries in production.",
          ],
          skills: [
            "Advanced proficiency with React 18, TypeScript, Tailwind CSS, and Vite.",
            "Extensive knowledge of React Query, REST/WebSocket APIs, and state management.",
            "In-depth knowledge of accessibility (WCAG), performance budgeting, browser internals.",
            "Superb analytical and debugging abilities for frontend performance issues.",
            "Great communication and collaboration skills with designers and backend engineers.",
            "Excellent time management across parallel feature tracks.",
          ],
          responsibilities: [
            "Build and maintain the cloud dashboard: device management, model marketplace, admin panels.",
            
            "Own the design system (Tailwind + shadcn/ui), accessibility, and performance budgets.",
            "Integrate real-time subscriptions, auth flows, and file storage in the UI layer.",
            "Write component tests and collaborate on E2E scripts with QA.",
          ],
        },
        {
          title: "Job Description — Electron / Desktop Developer",
          dept: "Product Team · 1 Headcount",
          color: "3B82F6",
          education: [
            "Bachelor's degree in Computer Science, Software Engineering, or a related field.",
            "Certifications in cross-platform desktop development are advantageous.",
          ],
          experience: [
            "At least 3 years' experience building cross-platform desktop apps with Electron.",
            "Experience integrating local AI runtimes (e.g., Ollama) or similar native tooling.",
            "Demonstrated experience with app signing, notarization, and release pipelines.",
          ],
          skills: [
            "Advanced proficiency with Electron, Node.js, and IPC (inter-process communication).",
            "Extensive knowledge of Ollama API, GGUF model loading, and local inference patterns.",
            "In-depth knowledge of cross-platform packaging (Windows, macOS, Linux) via electron-builder.",
            "Superb problem-solving abilities for offline-first sync and conflict resolution.",
            "Great communication skills to coordinate with cloud backend and ML teams.",
            "Excellent organizational abilities for managing multi-platform release tracks.",
          ],
          responsibilities: [
            "Architect and develop the Fideon Fabric Electron desktop app (Windows, macOS, Linux).",
            "Integrate Ollama runtime for on-device local AI inference without cloud dependency.",
            "Build offline-first sync queue, model download manager, and auto-update pipeline.",
            "Implement secure IPC between renderer and main process.",
            "Handle app signing, notarization, and distribution via electron-builder.",
          ],
        },
        {
          title: "Job Description — Backend / API Developer",
          dept: "Product Team · 1 Headcount",
          color: "22C55E",
          education: [
            "Bachelor's degree in Computer Science, Information Systems, or a related field.",
            "Master's degree in Distributed Systems or Cloud Architecture is advantageous.",
          ],
          experience: [
            "At least 4 years' experience as a Backend or API Developer.",
            "Experience designing multi-tenant SaaS backends with robust security controls.",
            "Proven experience with PostgreSQL, REST APIs, and serverless functions at scale.",
          ],
          skills: [
            "Advanced proficiency with TypeScript / Deno, PostgreSQL, and Docker.",
            "Extensive knowledge of REST/GraphQL API design, versioning, and documentation.",
            "In-depth knowledge of Row Level Security, multi-tenant data isolation, and audit logging.",
            "Superb analytical and architecture abilities for distributed backend systems.",
            "Great communication and collaboration skills for cross-functional API contracts.",
            "Excellent time management and ability to maintain API SLA commitments.",
          ],
          responsibilities: [
            "Design and build REST APIs and Edge Functions for device, model, and workflow management.",
            "Implement device check-in, model allocation sync engine, and federated learning.",
            "Set up RLS policies, multi-tenant data isolation, and comprehensive audit logging.",
            "Integrate third-party services: AI model APIs, email, webhooks, payment processing.",
            "Own API documentation, versioning strategy, and SLA monitoring dashboards.",
          ],
        },
      ] as Array<{ title: string; dept: string; color: string; education: string[]; experience: string[]; skills: string[]; responsibilities: string[] }>).map((jd) => ({
        title: jd.title,
        subtitle: `${jd.dept} | NeuraPod Private AI Tenant`,
        build: (slide: ReturnType<typeof pptx.addSlide>) => {
          const leftSections = [
            { label: "Education", items: jd.education },
            { label: "Experience Required", items: jd.experience },
          ];
          const rightSections = [
            { label: "Required Skills", items: jd.skills },
            { label: "Key Responsibilities", items: jd.responsibilities },
          ];

          // Dept badge
          addCard(slide, 0.4, 1.25, 4.0, 0.36, { fill: jd.color, border: jd.color });
          slide.addText(jd.dept, { x: 0.55, y: 1.29, w: 3.8, h: 0.28, fontSize: 10, bold: true, color: COLORS.white });

          const renderCol = (sections: typeof leftSections, startX: number) => {
            let curY = 1.75;
            sections.forEach((sec) => {
              addCard(slide, startX, curY, 5.85, 0.28, { fill: jd.color, border: jd.color });
              slide.addText(sec.label.toUpperCase(), { x: startX + 0.12, y: curY + 0.04, w: 5.65, h: 0.2, fontSize: 8.5, bold: true, color: COLORS.white });
              curY += 0.3;
              sec.items.forEach((item) => {
                slide.addText(`   ${item}`, { x: startX + 0.12, y: curY, w: 5.65, h: 0.31, fontSize: 9, color: COLORS.darkText });
                curY += 0.32;
              });
              curY += 0.14;
            });
          };

          renderCol(leftSections, 0.4);
          renderCol(rightSections, 6.55);
        },
      })),
      {
        title: "", subtitle: "",
        build: (slide) => {
          slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: "100%", h: "100%", fill: { color: COLORS.dark } });
          slide.addText("$8M Series A", { x: 1, y: 1.0, w: 11, h: 1.2, fontSize: 48, bold: true, color: COLORS.primary, align: "center" });
          slide.addText("24-month runway to achieve profitability", { x: 1, y: 2.2, w: 11, h: 0.6, fontSize: 18, color: "AAAACC", align: "center" });
          [
            { title: "Use of Funds", items: ["45% Engineering & Product", "30% Sales & Marketing", "15% Infrastructure", "10% G&A"], x: 1.5 },
            { title: "Key Milestones (18 Mo)", items: ["150+ enterprise customers", "15,000+ active devices", "75+ domain models", "$20M ARR"], x: 7 },
          ].forEach((col) => {
            addCard(slide, col.x, 3.2, 4.5, 3.0, { fill: "2A2A4E" });
            slide.addText(col.title, { x: col.x + 0.3, y: 3.3, w: 3.9, h: 0.4, fontSize: 14, bold: true, color: COLORS.white });
            col.items.forEach((item, j) => {
              slide.addText(`•  ${item}`, { x: col.x + 0.3, y: 3.9 + j * 0.4, w: 3.9, h: 0.35, fontSize: 12, color: "CCCCDD" });
            });
          });
          slide.addText("Join us in building the future of private, compliant enterprise AI", { x: 1, y: 6.5, w: 11, h: 0.5, fontSize: 14, color: "AAAACC", align: "center" });
        },
      },
    ];

    console.log(`PPTX Export: ${slideData.length} slides in slideData, ${totalSlides} UI slides`);
    slideData.forEach((sd, index) => {
      try {
        const pptSlide = pptx.addSlide();
        // Add header for content slides (not title/closing)
        if (sd.title) {
          addHeader(pptSlide, sd.title, sd.subtitle);
        }
        sd.build(pptSlide);
        addFooter(pptSlide, index + 1, slideData.length);
        console.log(`PPTX: Slide ${index + 1} built: "${sd.title}"`);
      } catch (err) {
        console.error(`PPTX: Error building slide ${index + 1} "${sd.title}":`, err);
      }
    });

    pptx.writeFile({ fileName: "NeuraPod_Cloud_Pitch_Deck.pptx" });
    toast.success(`Pitch deck exported: ${slideData.length} slides`);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-primary/5 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header with Export Button */}
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">NeuraPod Private AI Tenant Investor Pitch Deck</h1>
          <div className="flex gap-3">
            <Button onClick={exportJDtoPDF} variant="outline" size="lg">
              <FileText className="mr-2 h-5 w-5" />
              Export JDs as PDF
            </Button>
            <Button onClick={exportToPPTX} variant="default" size="lg">
              <Download className="mr-2 h-5 w-5" />
              Export to PPTX
            </Button>
          </div>
        </div>

        {/* Slide Container */}
        <Card className="min-h-[600px] p-12 mb-8 shadow-2xl">
          <div className="mb-8">
            <h2 className="text-4xl font-bold mb-2">{slides[currentSlide].title}</h2>
            <p className="text-xl text-muted-foreground">{slides[currentSlide].subtitle}</p>
          </div>
          <div className="min-h-[400px]">{slides[currentSlide].content}</div>
        </Card>

        {/* Navigation */}
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            size="lg"
            onClick={prevSlide}
            disabled={currentSlide === 0}
          >
            <ChevronLeft className="mr-2" />
            Previous
          </Button>

          <div className="flex gap-2">
            {slides.map((_, index) => (
              <button
                key={index}
                onClick={() => goToSlide(index)}
                className={`w-3 h-3 rounded-full transition-all ${
                  currentSlide === index
                    ? "bg-primary w-8"
                    : "bg-muted-foreground/30 hover:bg-muted-foreground/50"
                }`}
              />
            ))}
          </div>

          <Button
            variant="outline"
            size="lg"
            onClick={nextSlide}
            disabled={currentSlide === slides.length - 1}
          >
            Next
            <ChevronRight className="ml-2" />
          </Button>
        </div>

        {/* Slide Counter */}
        <div className="text-center mt-4 text-muted-foreground">
          Slide {currentSlide + 1} of {slides.length}
        </div>
      </div>
    </div>
  );
}
