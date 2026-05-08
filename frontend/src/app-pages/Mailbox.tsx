import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Mail,
  MailOpen,
  Paperclip,
  FileText,
  Clock,
  Star,
  StarOff,
  ArrowLeft,
  Download,
  Building2,
} from "lucide-react";

interface EmailAttachment {
  name: string;
  type: string;
  size: string;
}

interface Email {
  id: string;
  from: string;
  fromEmail: string;
  carrier: string;
  subject: string;
  preview: string;
  body: string;
  date: string;
  read: boolean;
  starred: boolean;
  attachments: EmailAttachment[];
  tags: string[];
}

const sampleEmails: Email[] = [
  {
    id: "1",
    from: "Progressive Commercial",
    fromEmail: "underwriting@progressive.com",
    carrier: "Progressive",
    subject: "Policy Renewal - Commercial Auto #PA-2026-44821",
    preview: "Your commercial auto policy is up for renewal. Please review the attached documents...",
    body: `Dear Agent,

Your client's Commercial Auto policy #PA-2026-44821 is approaching its renewal date of March 15, 2026. Please find attached the renewal proposal with updated premium and coverage details.

Key Changes:
• Premium adjusted to $12,450/yr (3.2% increase)
• Fleet discount applied for 5+ vehicles
• Added hired/non-owned auto coverage
• Umbrella eligibility confirmed

Please review the attached renewal documents and confirm acceptance by March 1, 2026.

Best regards,
Progressive Commercial Underwriting`,
    date: "2026-02-08",
    read: false,
    starred: true,
    attachments: [
      { name: "PA-2026-44821_Renewal.pdf", type: "pdf", size: "2.4 MB" },
      { name: "Coverage_Schedule.pdf", type: "pdf", size: "890 KB" },
    ],
    tags: ["Renewal", "Auto"],
  },
  {
    id: "2",
    from: "Travelers Insurance",
    fromEmail: "submissions@travelers.com",
    carrier: "Travelers",
    subject: "New Business Quote - BOP Package #TRV-BOP-88192",
    preview: "We're pleased to provide the following quote for your client's Business Owners Policy...",
    body: `Dear Agent,

Thank you for the submission. We are pleased to offer a competitive quote for the Business Owners Policy (BOP) for ABC Hardware LLC.

Quote Summary:
• Annual Premium: $8,750
• Property Coverage: $500,000
• General Liability: $1,000,000/$2,000,000
• Business Income: 12 months actual loss sustained
• Equipment Breakdown included

This quote is valid for 30 days. Please see the attached proposal and application for binding.

Sincerely,
Travelers Underwriting Team`,
    date: "2026-02-07",
    read: false,
    starred: false,
    attachments: [
      { name: "TRV-BOP-88192_Quote.pdf", type: "pdf", size: "1.8 MB" },
      { name: "BOP_Application.pdf", type: "pdf", size: "1.2 MB" },
      { name: "Coverage_Comparison.xlsx", type: "xlsx", size: "340 KB" },
    ],
    tags: ["New Business", "BOP"],
  },
  {
    id: "3",
    from: "Hartford Underwriting",
    fromEmail: "claims@thehartford.com",
    carrier: "Hartford",
    subject: "Claim Status Update - WC Claim #HF-CLM-2026-1193",
    preview: "This is to inform you that the workers' compensation claim has been reviewed...",
    body: `Dear Agent,

This is an update regarding Workers' Compensation Claim #HF-CLM-2026-1193 for your insured, Delta Construction Inc.

Claim Status: Under Medical Review
• Date of Loss: January 22, 2026
• Claimant: John Martinez
• Injury: Lower back strain
• Reserve: $35,000
• Medical payments to date: $4,200

The independent medical examination is scheduled for February 20, 2026. Updated reserve and status reports are attached.

Please contact us if you have any questions.

Hartford Claims Department`,
    date: "2026-02-06",
    read: true,
    starred: false,
    attachments: [
      { name: "HF-CLM-2026-1193_Status.pdf", type: "pdf", size: "560 KB" },
    ],
    tags: ["Claims", "Workers Comp"],
  },
  {
    id: "4",
    from: "Chubb Commercial Lines",
    fromEmail: "cpl@chubb.com",
    carrier: "Chubb",
    subject: "Endorsement Issued - Cyber Liability #CB-CYB-55210",
    preview: "The requested endorsement to add ransomware coverage has been processed...",
    body: `Dear Agent,

The endorsement to policy #CB-CYB-55210 has been processed and is effective February 1, 2026.

Endorsement Details:
• Added: Ransomware Extortion Coverage - $250,000 sublimit
• Added: Social Engineering Fraud - $100,000 sublimit
• Additional Premium: $1,850 (prorated)
• New Annual Premium: $14,200

The updated policy documents and endorsement forms are attached. Please deliver to your insured.

Thank you,
Chubb Commercial Lines`,
    date: "2026-02-05",
    read: true,
    starred: true,
    attachments: [
      { name: "CB-CYB-55210_Endorsement.pdf", type: "pdf", size: "1.1 MB" },
      { name: "Updated_Dec_Page.pdf", type: "pdf", size: "420 KB" },
    ],
    tags: ["Endorsement", "Cyber"],
  },
  {
    id: "5",
    from: "Liberty Mutual",
    fromEmail: "renewals@libertymutual.com",
    carrier: "Liberty Mutual",
    subject: "Non-Renewal Notice - GL Policy #LM-GL-2025-7743",
    preview: "We regret to inform you that the following general liability policy will not be renewed...",
    body: `Dear Agent,

Please be advised that General Liability policy #LM-GL-2025-7743 for Apex Roofing LLC will not be renewed at its expiration date of April 1, 2026.

Reason: Adverse loss experience (3 claims in 24 months totaling $187,000)

This notice is provided 60 days in advance per state requirements. We recommend securing replacement coverage promptly.

The loss run report and non-renewal notice letter for your client are attached.

Liberty Mutual Underwriting`,
    date: "2026-02-04",
    read: true,
    starred: false,
    attachments: [
      { name: "LM-GL-7743_NonRenewal.pdf", type: "pdf", size: "780 KB" },
      { name: "Loss_Run_Report.pdf", type: "pdf", size: "1.5 MB" },
    ],
    tags: ["Non-Renewal", "GL"],
  },
  {
    id: "6",
    from: "Nationwide E&S",
    fromEmail: "surplus@nationwide.com",
    carrier: "Nationwide",
    subject: "Surplus Lines Quote - Liquor Liability #NW-SL-29104",
    preview: "Please find attached the surplus lines quote for the restaurant liquor liability...",
    body: `Dear Agent,

We have completed our review of the submission for Happy Hour Restaurant Group. Please find the surplus lines quote below.

Quote Details:
• Coverage: Liquor Liability
• Limit: $1,000,000 per occurrence / $2,000,000 aggregate
• Annual Premium: $6,200
• Deductible: $5,000 per claim
• Surplus Lines Tax: $310

Special Conditions:
• Alcohol sales must not exceed 60% of total revenue
• Security staff required after 10 PM
• Annual liquor license verification

Quote valid for 15 days. See attached for full terms.

Nationwide Excess & Surplus`,
    date: "2026-02-03",
    read: true,
    starred: false,
    attachments: [
      { name: "NW-SL-29104_Quote.pdf", type: "pdf", size: "2.1 MB" },
    ],
    tags: ["Surplus Lines", "Liquor"],
  },
];

const tagColors: Record<string, string> = {
  Renewal: "bg-blue-500/10 text-blue-600 border-blue-500/20",
  "New Business": "bg-green-500/10 text-green-600 border-green-500/20",
  Claims: "bg-amber-500/10 text-amber-600 border-amber-500/20",
  Endorsement: "bg-purple-500/10 text-purple-600 border-purple-500/20",
  "Non-Renewal": "bg-red-500/10 text-red-600 border-red-500/20",
  "Surplus Lines": "bg-teal-500/10 text-teal-600 border-teal-500/20",
};

export default function Mailbox() {
  const [emails, setEmails] = useState<Email[]>(sampleEmails);
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null);
  const [filter, setFilter] = useState<string>("all");

  const unreadCount = emails.filter((e: any) => !e.read).length;

  let filteredEmails = emails;
  if (filter === "unread") {
    filteredEmails = emails.filter((e: any) => !e.read);
  } else if (filter === "starred") {
    filteredEmails = emails.filter((e: any) => e.starred);
  } else if (filter === "attachments") {
    filteredEmails = emails.filter((e: any) => e.attachments.length > 0);
  }

  const openEmail = (email: Email) => {
    setEmails((prev) =>
      prev.map((e: any) => (e.id === email.id ? { ...e, read: true } : e))
    );
    setSelectedEmail({ ...email, read: true });
  };

  const toggleStar = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setEmails((prev) =>
      prev.map((em: any) => (em.id === id ? { ...em, starred: !em.starred } : em))
    );
    if (selectedEmail?.id === id) {
      setSelectedEmail((prev) => prev ? { ...prev, starred: !prev.starred } : null);
    }
  };

  const getFileIcon = (_type: string) => {
    return <FileText className="h-4 w-4 text-red-500" />;
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Mailbox
        </h1>
        <p className="text-muted-foreground mt-1">
          Carrier communications and policy documents
        </p>
      </div>

      <div className="flex gap-2 flex-wrap">
        {[
          { key: "all", label: `All (${emails.length})` },
          { key: "unread", label: `Unread (${unreadCount})` },
          { key: "starred", label: "Starred" },
          { key: "attachments", label: "With Attachments" },
        ].map((f: any) => (
          <Button
            key={f.key}
            variant={filter === f.key ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </Button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 min-h-[600px]">
        {/* Email List */}
        <Card className="lg:col-span-2 bg-card border-border shadow-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Mail className="h-4 w-4 text-primary" />
              Inbox
              {unreadCount > 0 && (
                <Badge variant="destructive" className="text-xs px-1.5 py-0">
                  {unreadCount}
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[550px]">
              {filteredEmails.map((email: any) => (
                <div
                  key={email.id}
                  onClick={() => openEmail(email)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      openEmail(email);
                    }
                  }}
                  role="button"
                  tabIndex={0}
                  aria-pressed={selectedEmail?.id === email.id}
                  className={`px-4 py-3 cursor-pointer border-b border-border transition-colors hover:bg-muted/50 ${
                    selectedEmail?.id === email.id ? "bg-primary/5 border-l-2 border-l-primary" : ""
                  } ${!email.read ? "bg-primary/[0.03]" : ""}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm truncate ${!email.read ? "font-semibold text-foreground" : "text-muted-foreground"}`}>
                          {email.from}
                        </span>
                        {!email.read && (
                          <div className="h-2 w-2 rounded-full bg-primary flex-shrink-0" />
                        )}
                      </div>
                      <p className={`text-sm truncate ${!email.read ? "font-medium text-foreground" : "text-muted-foreground"}`}>
                        {email.subject}
                      </p>
                      <p className="text-xs text-muted-foreground truncate mt-0.5">
                        {email.preview}
                      </p>
                      <div className="flex items-center gap-2 mt-1.5">
                        {email.tags.map((tag: any) => (
                          <Badge
                            key={tag}
                            variant="outline"
                            className={`text-[10px] px-1.5 py-0 ${tagColors[tag] || ""}`}
                          >
                            {tag}
                          </Badge>
                        ))}
                        {email.attachments.length > 0 && (
                          <span className="flex items-center gap-0.5 text-[10px] text-muted-foreground">
                            <Paperclip className="h-3 w-3" />
                            {email.attachments.length}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                        {new Date(email.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                      </span>
                      <button onClick={(e) => toggleStar(email.id, e)} className="text-muted-foreground hover:text-amber-500 transition-colors">
                        {email.starred ? (
                          <Star className="h-3.5 w-3.5 fill-amber-500 text-amber-500" />
                        ) : (
                          <StarOff className="h-3.5 w-3.5" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Email Detail */}
        <Card className="lg:col-span-3 bg-card border-border shadow-card">
          {selectedEmail ? (
            <>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="space-y-1 flex-1 min-w-0">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="lg:hidden mb-2 -ml-2"
                      onClick={() => setSelectedEmail(null)}
                    >
                      <ArrowLeft className="h-4 w-4 mr-1" /> Back
                    </Button>
                    <CardTitle className="text-lg leading-tight">
                      {selectedEmail.subject}
                    </CardTitle>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Building2 className="h-4 w-4" />
                      <span className="font-medium text-foreground">
                        {selectedEmail.from}
                      </span>
                      <span>&lt;{selectedEmail.fromEmail}&gt;</span>
                    </div>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      {new Date(selectedEmail.date).toLocaleDateString("en-US", {
                        weekday: "long",
                        month: "long",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    {selectedEmail.tags.map((tag: any) => (
                      <Badge
                        key={tag}
                        variant="outline"
                        className={tagColors[tag] || ""}
                      >
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
              </CardHeader>
              <Separator />
              <CardContent className="pt-4">
                <ScrollArea className="h-[350px]">
                  <pre className="whitespace-pre-wrap text-sm text-foreground font-sans leading-relaxed">
                    {selectedEmail.body}
                  </pre>
                </ScrollArea>

                {selectedEmail.attachments.length > 0 && (
                  <div className="mt-6 space-y-2">
                    <Separator />
                    <p className="text-sm font-medium text-foreground flex items-center gap-2 pt-2">
                      <Paperclip className="h-4 w-4" />
                      Attachments ({selectedEmail.attachments.length})
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {selectedEmail.attachments.map((att: any) => (
                        <div
                          key={`${att.name}-${att.size}`}
                          className="flex items-center gap-3 p-3 rounded-lg border border-border bg-muted/30 hover:bg-muted/60 transition-colors group"
                        >
                          {getFileIcon(att.type)}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate text-foreground">
                              {att.name}
                            </p>
                            <p className="text-xs text-muted-foreground">{att.size}</p>
                          </div>
                          <Button variant="ghost" size="icon" className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity">
                            <Download className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </>
          ) : (
            <CardContent className="flex flex-col items-center justify-center h-full py-20">
              <MailOpen className="h-16 w-16 text-muted-foreground/30 mb-4" />
              <p className="text-muted-foreground font-medium">Select an email to read</p>
              <p className="text-sm text-muted-foreground/70">
                Choose a message from the inbox
              </p>
            </CardContent>
          )}
        </Card>
      </div>
    </div>
  );
}
