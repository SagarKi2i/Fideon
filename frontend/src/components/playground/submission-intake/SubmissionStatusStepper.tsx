import { Check, Clock, Filter, UserCheck, DollarSign, XCircle } from "lucide-react";
import { ParsedSubmission } from "./types";

interface SubmissionStatusStepperProps {
  status: ParsedSubmission["status"];
}

const steps = [
  { id: "received", label: "Received", icon: Clock },
  { id: "triaged", label: "Triaged", icon: Filter },
  { id: "assigned", label: "Assigned", icon: UserCheck },
  { id: "quoted", label: "Quoted", icon: DollarSign },
];

export default function SubmissionStatusStepper({ status }: SubmissionStatusStepperProps) {
  const currentIndex = steps.findIndex((s) => s.id === status);
  const isDeclined = status === "declined";

  return (
    <div className="flex items-center justify-between w-full max-w-xl mx-auto py-4">
      {steps.map((step, index) => {
        const Icon = step.icon;
        const isCompleted = index < currentIndex;
        const isCurrent = index === currentIndex;
        const isPending = index > currentIndex;

        return (
          <div key={step.id} className="flex items-center flex-1">
            <div className="flex flex-col items-center">
              <div
                className={`
                  w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300
                  ${isCompleted ? "bg-green-500 text-white shadow-lg shadow-green-500/30" : ""}
                  ${isCurrent && !isDeclined ? "bg-primary text-primary-foreground shadow-lg shadow-primary/30 ring-4 ring-primary/20" : ""}
                  ${isCurrent && isDeclined ? "bg-destructive text-destructive-foreground shadow-lg shadow-destructive/30" : ""}
                  ${isPending ? "bg-muted text-muted-foreground" : ""}
                `}
              >
                {isCompleted ? (
                  <Check className="h-5 w-5" />
                ) : isCurrent && isDeclined ? (
                  <XCircle className="h-5 w-5" />
                ) : (
                  <Icon className="h-5 w-5" />
                )}
              </div>
              <span
                className={`
                  mt-2 text-xs font-medium transition-colors
                  ${isCompleted || isCurrent ? "text-foreground" : "text-muted-foreground"}
                `}
              >
                {step.label}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div className="flex-1 h-0.5 mx-2 mt-[-20px]">
                <div
                  className={`h-full transition-all duration-500 ${
                    isCompleted ? "bg-green-500" : "bg-muted"
                  }`}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
