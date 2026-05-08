import { Badge } from "@/components/ui/badge";
import { 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  Info,
  ArrowRight,
  DollarSign,
  Shield,
  FileText,
  Clock,
  Target
} from "lucide-react";

interface MarkdownRendererProps {
  readonly content: string;
}

type StatusPattern = {
  pattern: RegExp;
  icon: typeof CheckCircle2;
  color: string;
  bg: string;
};

type StatusTone = "positive" | "negative" | "neutral";

const STATUS_PATTERNS: StatusPattern[] = [
  { pattern: /^✓\s*(.+)$/u, icon: CheckCircle2, color: "text-green-600", bg: "bg-green-500/10" },
  { pattern: /^⚠(?:️)?\s*(.+)$/u, icon: AlertTriangle, color: "text-amber-600", bg: "bg-amber-500/10" },
  { pattern: /^🚩\s*(.+)$/u, icon: AlertTriangle, color: "text-red-600", bg: "bg-red-500/10" },
  { pattern: /^❌\s*(.+)$/u, icon: XCircle, color: "text-red-600", bg: "bg-red-500/10" },
];

const STATUS_PREFIX_RE = /^[✓⚠🚩❌]\s*/u;
const BULLET_PREFIX_RE = /^[•\-*]\s*/;
const NUMBERED_LIST_RE = /^\d+[.)]\s/;
const LABEL_VALUE_RE = /:/;
const BOLD_RE = /\*\*([^*]+)\*\*/;

function resolveStatusTone(value: string): StatusTone {
  const lower = value.toLowerCase();
  const isPositive =
    lower.includes("approved") || lower.includes("compliant") || lower.includes("active") || value.includes("✓");
  if (isPositive) return "positive";
  const isNegative =
    lower.includes("denied") || lower.includes("rejected") || lower.includes("failed") || value.includes("❌");
  if (isNegative) return "negative";
  return "neutral";
}

function statusToneClasses(tone: StatusTone): { container: string; badge: string } {
  if (tone === "positive") {
    return {
      container: "bg-green-500/5 border-green-500/30",
      badge: "bg-green-500/10 text-green-600 border-green-500/30",
    };
  }
  if (tone === "negative") {
    return {
      container: "bg-red-500/5 border-red-500/30",
      badge: "bg-red-500/10 text-red-600 border-red-500/30",
    };
  }
  return {
    container: "bg-primary/5 border-primary/30",
    badge: "bg-primary/10 text-primary border-primary/30",
  };
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const parseContent = (text: string) => {
    const lines = text.split('\n');
    const elements: JSX.Element[] = [];
    let currentList: string[] = [];
    let listType: 'bullet' | 'numbered' | null = null;

    const flushList = () => {
      if (currentList.length > 0 && listType) {
        elements.push(
          <div key={`list-${elements.length}`} className="space-y-2 my-4">
            {currentList.map((item: any, idx: any) => (
              <div key={`${item}-${idx}`} className="flex items-start gap-3 pl-2">
                {listType === 'numbered' ? (
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 text-primary text-xs flex items-center justify-center font-semibold">
                    {idx + 1}
                  </span>
                ) : (
                  <ArrowRight className="h-4 w-4 text-primary flex-shrink-0 mt-0.5" />
                )}
                <span className="text-foreground leading-relaxed">{parseInlineFormatting(item)}</span>
              </div>
            ))}
          </div>
        );
        currentList = [];
        listType = null;
      }
    };

    const parseInlineFormatting = (text: string): JSX.Element => {
      for (const { pattern, icon: Icon, color, bg } of STATUS_PATTERNS) {
        const match = pattern.exec(text);
        if (match) {
          const matchedText = match[1] ?? text;
          return (
            <span className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg ${bg}`}>
              <Icon className={`h-4 w-4 ${color} flex-shrink-0`} />
              <span className={color}>{parseInlineText(matchedText)}</span>
            </span>
          );
        }
      }

      return <>{parseInlineText(text)}</>;
    };

    const parseInlineText = (text: string): JSX.Element => {
      // Handle bold text with proper regex that handles multiple occurrences
      const parts: (string | JSX.Element)[] = [];
      let remaining = text;
      let keyIndex = 0;

      while (remaining.length > 0) {
        const boldMatch = BOLD_RE.exec(remaining);
        
        if (boldMatch && boldMatch.index !== undefined) {
          // Add text before the bold
          if (boldMatch.index > 0) {
            parts.push(remaining.slice(0, boldMatch.index));
          }
          // Add the bold text
          parts.push(
            <strong key={`bold-${keyIndex++}`} className="font-semibold text-foreground">
              {boldMatch[1]}
            </strong>
          );
          // Continue with remaining text
          remaining = remaining.slice(boldMatch.index + boldMatch[0].length);
        } else {
          // No more bold text, add the rest
          parts.push(remaining);
          break;
        }
      }

      return <>{parts.map((part: any, idx: any) =>
        typeof part === 'string' ? <span key={`text-${idx}`}>{part}</span> : part
      )}</>;
    };

    const getHeadingIcon = (text: string) => {
      const lowerText = text.toLowerCase();
      if (lowerText.includes('premium') || lowerText.includes('price') || lowerText.includes('cost')) return DollarSign;
      if (lowerText.includes('coverage') || lowerText.includes('protection') || lowerText.includes('security')) return Shield;
      if (lowerText.includes('recommendation') || lowerText.includes('suggest')) return Target;
      if (lowerText.includes('document') || lowerText.includes('report') || lowerText.includes('summary')) return FileText;
      if (lowerText.includes('next step') || lowerText.includes('action') || lowerText.includes('timeline')) return Clock;
      return Info;
    };

    lines.forEach((line: any, lineIdx: any) => {
      const trimmedLine = line.trim();

      // Skip empty lines
      if (!trimmedLine) {
        flushList();
        return;
      }

      // Main heading (## or **)
      if (trimmedLine.startsWith('##') || (trimmedLine.startsWith('**') && trimmedLine.endsWith('**') && !trimmedLine.includes(':') && trimmedLine.length < 80)) {
        flushList();
        const headingText = trimmedLine.replace(/^##\s*/, '').replace(/^\*\*/, '').replace(/\*\*$/, '');
        const Icon = getHeadingIcon(headingText);
        elements.push(
          <div key={lineIdx} className="flex items-center gap-3 mt-6 mb-4 first:mt-0">
            <div className="p-2 rounded-lg bg-primary/10">
              <Icon className="h-5 w-5 text-primary" />
            </div>
            <h3 className="text-lg font-semibold text-foreground">{headingText}</h3>
          </div>
        );
        return;
      }

      // Section with label and value (Label: Value)
      if (
        LABEL_VALUE_RE.test(trimmedLine) &&
        !trimmedLine.startsWith("•") &&
        !trimmedLine.startsWith("-") &&
        !NUMBERED_LIST_RE.test(trimmedLine)
      ) {
        const colonIndex = trimmedLine.indexOf(':');
        const label = trimmedLine.slice(0, colonIndex).replace(/^\*\*/, '').replace(/\*\*$/, '');
        const value = trimmedLine.slice(colonIndex + 1).trim();
        
        // Check if this is a status line
        if (label.toLowerCase().includes('status') || label.toLowerCase().includes('eligibility') || label.toLowerCase().includes('compliance')) {
          flushList();
          const tone = resolveStatusTone(value);
          const toneClasses = statusToneClasses(tone);
          elements.push(
            <div key={lineIdx} className={`flex items-center justify-between p-4 rounded-xl border ${toneClasses.container} my-3`}>
              <span className="font-medium text-muted-foreground">{label}</span>
              <Badge className={toneClasses.badge}>
                {tone === "positive" && <CheckCircle2 className="h-3 w-3 mr-1" />}
                {tone === "negative" && <XCircle className="h-3 w-3 mr-1" />}
                {value.replace(STATUS_PREFIX_RE, "").trim()}
              </Badge>
            </div>
          );
          return;
        }

        // Regular label:value pair
        if (label.length < 40 && value) {
          flushList();
          elements.push(
            <div key={lineIdx} className="flex items-start gap-3 py-2 px-3 rounded-lg hover:bg-muted/30 transition-colors">
              <span className="font-medium text-muted-foreground min-w-[140px] flex-shrink-0">{label}:</span>
              <span className="text-foreground">{parseInlineFormatting(value)}</span>
            </div>
          );
          return;
        }
      }

      // Bullet points
      if (trimmedLine.startsWith('•') || trimmedLine.startsWith('-') || trimmedLine.startsWith('*')) {
        if (listType !== 'bullet') {
          flushList();
          listType = 'bullet';
        }
        currentList.push(trimmedLine.replace(BULLET_PREFIX_RE, ''));
        return;
      }

      // Numbered list
      if (NUMBERED_LIST_RE.test(trimmedLine)) {
        if (listType !== 'numbered') {
          flushList();
          listType = 'numbered';
        }
        currentList.push(trimmedLine.replace(/^\d+[.)]\s*/, ''));
        return;
      }

      // Status lines with checkmarks or warnings
      if (trimmedLine.startsWith('✓') || trimmedLine.startsWith('⚠') || trimmedLine.startsWith('🚩') || trimmedLine.startsWith('❌')) {
        flushList();
        elements.push(
          <div key={lineIdx} className="my-2">
            {parseInlineFormatting(trimmedLine)}
          </div>
        );
        return;
      }

      // Regular paragraph
      flushList();
      elements.push(
        <p key={lineIdx} className="text-foreground leading-relaxed my-3">
          {parseInlineFormatting(trimmedLine)}
        </p>
      );
    });

    flushList();
    return elements;
  };

  return (
    <div className="space-y-1 animate-in fade-in duration-500">
      {parseContent(content)}
    </div>
  );
}
