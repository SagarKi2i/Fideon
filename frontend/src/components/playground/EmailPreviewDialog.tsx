import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { 
  Send, 
  Mail, 
  Shield,
  DollarSign,
  Calendar,
  CheckCircle2,
  Loader2
} from "lucide-react";

interface EmailPreviewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSend: () => void;
  isSending?: boolean;
  proposalData: {
    recipientName: string;
    recipientEmail: string;
    carrierName: string;
    premium: number;
    coverage: string;
    deductible: number;
    insuranceType: string;
    proposalNumber: string;
    effectiveDate: Date;
  };
}

export default function EmailPreviewDialog({
  open,
  onOpenChange,
  onSend,
  isSending = false,
  proposalData
}: EmailPreviewDialogProps) {
  const {
    recipientName,
    recipientEmail,
    carrierName,
    premium,
    coverage,
    deductible,
    insuranceType,
    proposalNumber,
    effectiveDate
  } = proposalData;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5 text-primary" />
            Email Preview
          </DialogTitle>
          <DialogDescription>
            Review the email before sending to the insured
          </DialogDescription>
        </DialogHeader>

        {/* Email Header Info */}
        <div className="bg-muted/30 rounded-lg p-4 space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground w-16">To:</span>
            <span className="font-medium">{recipientName} &lt;{recipientEmail ?? 'email@example.com'}&gt;</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground w-16">From:</span>
            <span className="font-medium">Fideon Insurance &lt;proposals@fideon.ai&gt;</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground w-16">Subject:</span>
            <span className="font-medium">Your Insurance Proposal from {carrierName} - #{proposalNumber}</span>
          </div>
        </div>

        <Separator />

        {/* Email Body Preview */}
        <div className="border rounded-lg overflow-hidden">
          {/* Email Header Banner */}
          <div className="bg-gradient-to-r from-primary to-primary/80 text-primary-foreground p-6 text-center">
            <div className="flex items-center justify-center gap-3 mb-2">
              <Shield className="h-8 w-8" />
              <h2 className="text-xl font-bold">Insurance Proposal</h2>
            </div>
            <p className="text-primary-foreground/80 text-sm">Proposal #{proposalNumber}</p>
          </div>

          {/* Email Content */}
          <div className="p-6 space-y-4 bg-background">
            <p className="text-foreground">Dear {recipientName},</p>
            
            <p className="text-muted-foreground">
              Thank you for your interest in obtaining insurance coverage. We are pleased to present 
              you with a competitive quote from <strong className="text-foreground">{carrierName}</strong> for 
              your <strong className="text-foreground">{insuranceType}</strong> needs.
            </p>

            {/* Quote Summary Card */}
            <div className="bg-muted/30 rounded-lg p-4 border border-border">
              <h3 className="font-semibold text-foreground mb-3 flex items-center gap-2">
                <Shield className="h-4 w-4 text-primary" />
                Quote Summary
              </h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="flex items-center gap-2">
                  <DollarSign className="h-4 w-4 text-green-600" />
                  <span className="text-muted-foreground">Annual Premium:</span>
                  <span className="font-bold text-green-600">${premium.toLocaleString()}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-blue-600" />
                  <span className="text-muted-foreground">Coverage:</span>
                  <span className="font-medium">{coverage}</span>
                </div>
                <div className="flex items-center gap-2">
                  <DollarSign className="h-4 w-4 text-amber-600" />
                  <span className="text-muted-foreground">Deductible:</span>
                  <span className="font-medium">${deductible.toLocaleString()}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-purple-600" />
                  <span className="text-muted-foreground">Effective:</span>
                  <span className="font-medium">
                    {effectiveDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                  </span>
                </div>
              </div>
            </div>

            <p className="text-muted-foreground">
              The complete proposal document is attached to this email for your review. Please take 
              a moment to review the coverage details, terms, and conditions.
            </p>

            {/* CTA Button */}
            <div className="text-center py-4">
              <div className="inline-block bg-primary text-primary-foreground px-6 py-3 rounded-lg font-medium">
                View Full Proposal
              </div>
            </div>

            <p className="text-muted-foreground text-sm">
              If you have any questions or would like to proceed with this coverage, please don't 
              hesitate to contact us. This proposal is valid for 30 days from the date of issue.
            </p>

            <Separator />

            <div className="text-sm text-muted-foreground">
              <p>Best regards,</p>
              <p className="font-medium text-foreground">Your Insurance Team</p>
              <p>Fideon Insurance Services</p>
            </div>
          </div>

          {/* Email Footer */}
          <div className="bg-muted/50 p-4 text-center text-xs text-muted-foreground border-t">
            <p>This is an automated email from Fideon Insurance Services.</p>
            <p>© 2025 Fideon. All rights reserved.</p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-sm text-muted-foreground bg-blue-500/5 p-3 rounded-lg border border-blue-500/20">
          <CheckCircle2 className="h-4 w-4 text-blue-600" />
          <span>The proposal PDF will be attached to this email automatically.</span>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button 
            onClick={onSend}
            disabled={isSending}
            className="bg-gradient-primary"
          >
            {isSending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Sending...
              </>
            ) : (
              <>
                <Send className="h-4 w-4 mr-2" />
                Send Email
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
