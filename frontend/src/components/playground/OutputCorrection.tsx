import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import {
  Edit3,
  Save,
  X,
  ThumbsUp,
  ThumbsDown,
  Star,
  CheckCircle2,
} from "lucide-react";
import { submitFeedback } from "@/lib/trainingApi";

interface OutputCorrectionProps {
  modelId: string;
  prompt: string;
  output: string;
  children: React.ReactNode;
}

export default function OutputCorrection({ modelId, prompt, output, children }: OutputCorrectionProps) {
  const { toast } = useToast();
  const [isEditing, setIsEditing] = useState(false);
  const [correctedText, setCorrectedText] = useState("");
  const [rating, setRating] = useState<number>(0);
  const [submitted, setSubmitted] = useState(false);
  const [thumbs, setThumbs] = useState<"up" | "down" | null>(null);

  // Always show correction UI — web users store locally, device users sync to cloud

  const handleStartEdit = () => {
    setCorrectedText(output);
    setIsEditing(true);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setCorrectedText("");
  };

  const handleSaveCorrection = async () => {
    if (!correctedText.trim()) return;

    try {
      await submitFeedback({
        model_id: modelId,
        prompt,
        original_response: output,
        corrected_response: correctedText !== output ? correctedText : undefined,
        rating: rating ?? undefined,
        feedback_type: correctedText !== output ? "correction" : "rating",
      });
      setSubmitted(true);
      setIsEditing(false);
      toast({
        title: "Correction saved",
        description: "Your correction will be used to improve this model",
      });
    } catch (error: any) {
      toast({
        title: "Error saving correction",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  const handleThumbsFeedback = async (type: "up" | "down") => {
    setThumbs(type);
    try {
      await submitFeedback({
        model_id: modelId,
        prompt,
        original_response: output,
        rating: type === "up" ? 5 : 1,
        feedback_type: "thumbs",
      });
      toast({
        title: "Feedback recorded",
        description: type === "up" ? "Glad it was helpful!" : "Thanks — this helps improve the model",
      });
    } catch {
      // Silent fail for quick feedback
    }
  };

  if (!output) return <>{children}</>;

  return (
    <div className="space-y-0">
      {/* Original output or editing view */}
      {isEditing ? (
        <div className="space-y-3 border rounded-lg p-4 bg-muted/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Edit3 className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium">Edit Output</span>
              <Badge variant="outline" className="text-xs">
                Corrections improve the model
              </Badge>
            </div>
            <Button variant="ghost" size="sm" onClick={handleCancel}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          <Textarea
            value={correctedText}
            onChange={(e) => setCorrectedText(e.target.value)}
            className="min-h-[200px] font-mono text-sm"
          />
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1">
              <span className="text-xs text-muted-foreground mr-2">Quality:</span>
              {[1, 2, 3, 4, 5].map((s) => (
                <Button
                  key={s}
                  variant={rating >= s ? "default" : "outline"}
                  size="sm"
                  className="h-7 w-7 p-0"
                  onClick={() => setRating(s)}
                >
                  <Star className={`h-3 w-3 ${rating >= s ? "fill-current" : ""}`} />
                </Button>
              ))}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleCancel}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleSaveCorrection}>
                <Save className="h-4 w-4 mr-1" />
                Save & Train
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <>
          {children}

          {/* Inline feedback bar */}
          {(
            <div className="flex items-center justify-between mt-3 pt-3 border-t border-border/50">
              <div className="flex items-center gap-2">
                {submitted ? (
                  <div className="flex items-center gap-1 text-sm text-green-600">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Correction saved for training</span>
                  </div>
                ) : (
                  <>
                    <span className="text-xs text-muted-foreground">Was this helpful?</span>
                    <Button
                      variant={thumbs === "up" ? "default" : "ghost"}
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => handleThumbsFeedback("up")}
                      disabled={thumbs !== null}
                    >
                      <ThumbsUp className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant={thumbs === "down" ? "default" : "ghost"}
                      size="sm"
                      className="h-7 w-7 p-0"
                      onClick={() => handleThumbsFeedback("down")}
                      disabled={thumbs !== null}
                    >
                      <ThumbsDown className="h-3.5 w-3.5" />
                    </Button>
                  </>
                )}
              </div>
              {!submitted && (
                <Button variant="outline" size="sm" onClick={handleStartEdit}>
                  <Edit3 className="h-3.5 w-3.5 mr-1" />
                  Edit & Train
                </Button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
