import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface AppetiteMatchGaugeProps {
  readonly score: number;
}

export default function AppetiteMatchGauge({ score }: AppetiteMatchGaugeProps) {
  const isStrong = score >= 80;
  const isModerate = score >= 60 && score < 80;
  const getScoreColor = () => {
    if (isStrong) return { bg: "from-green-500 to-emerald-500", text: "text-green-500", shadow: "shadow-green-500/30" };
    if (isModerate) return { bg: "from-amber-500 to-orange-500", text: "text-amber-500", shadow: "shadow-amber-500/30" };
    return { bg: "from-red-500 to-rose-500", text: "text-red-500", shadow: "shadow-red-500/30" };
  };

  const getScoreLabel = () => {
    if (score >= 80) return { label: "Strong Match", icon: TrendingUp, variant: "default" as const };
    if (score >= 60) return { label: "Moderate Match", icon: Minus, variant: "secondary" as const };
    return { label: "Review Required", icon: TrendingDown, variant: "destructive" as const };
  };

  const colors = getScoreColor();
  const scoreInfo = getScoreLabel();
  const ScoreIcon = scoreInfo.icon;
  const getGradientClasses = () => {
    if (isStrong) return { start: "text-green-500", end: "text-emerald-400" };
    if (isModerate) return { start: "text-amber-500", end: "text-orange-400" };
    return { start: "text-red-500", end: "text-rose-400" };
  };
  const gradientClasses = getGradientClasses();

  // Calculate the arc for the gauge
  const radius = 60;
  const circumference = Math.PI * radius;
  const progress = (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-36 h-20 overflow-hidden">
        <svg className="w-36 h-36 -mt-2" viewBox="0 0 140 80">
          {/* Background arc */}
          <path
            d="M 10 70 A 60 60 0 0 1 130 70"
            fill="none"
            stroke="currentColor"
            strokeWidth="12"
            strokeLinecap="round"
            className="text-muted"
          />
          {/* Progress arc */}
          <path
            d="M 10 70 A 60 60 0 0 1 130 70"
            fill="none"
            stroke="url(#gaugeGradient)"
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={`${progress} ${circumference}`}
            className="transition-all duration-1000 ease-out"
          />
          <defs>
            <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" className={gradientClasses.start} stopColor="currentColor" />
              <stop offset="100%" className={gradientClasses.end} stopColor="currentColor" />
            </linearGradient>
          </defs>
        </svg>
        
        {/* Score display */}
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-1">
          <span className={`text-4xl font-bold ${colors.text}`}>{score}%</span>
        </div>
      </div>
      
      <Badge variant={scoreInfo.variant} className="mt-2 gap-1">
        <ScoreIcon className="h-3.5 w-3.5" />
        {scoreInfo.label}
      </Badge>
    </div>
  );
}
