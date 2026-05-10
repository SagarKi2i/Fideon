import { HelpCircle } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface InfoTooltipProps {
  content: string;
  side?: "top" | "right" | "bottom" | "left";
  className?: string;
  iconClassName?: string;
}

export function InfoTooltip({ 
  content, 
  side = "top", 
  className,
  iconClassName 
}: InfoTooltipProps) {
  return (
    <Tooltip delayDuration={200}>
      <TooltipTrigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex items-center justify-center rounded-full text-muted-foreground hover:text-primary transition-colors focus:outline-none focus:ring-2 focus:ring-primary/20",
            className
          )}
        >
          <HelpCircle className={cn("h-4 w-4", iconClassName)} />
          <span className="sr-only">Help</span>
        </button>
      </TooltipTrigger>
      <TooltipContent 
        side={side} 
        className="max-w-[280px] text-sm"
      >
        <p>{content}</p>
      </TooltipContent>
    </Tooltip>
  );
}
