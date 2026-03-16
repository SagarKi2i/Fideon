import { HelpCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { FideonLogo } from "@/components/FideonLogo";

const faqs = [
  {
    question: "What is Fideon OS?",
    answer: "Fideon OS is a platform with specialized AI models designed for specific insurance workflows. Each pod is optimized for tasks like document retrieval, quote generation, policy comparison, or claims processing. You can activate multiple pods from the marketplace to automate different parts of your workflow."
  },
  {
    question: "How do I activate an AI Pod?",
    answer: "Navigate to the Marketplace from the sidebar, browse available pods by domain (insurance, healthcare, etc.), and click 'Activate' on any pod you want to use. Once activated, the pod will appear on your dashboard and in the playground."
  },
  {
    question: "What is the Playground?",
    answer: "The Playground is your interactive workspace where you can test and use your activated AI pods. Select a model from the dropdown, fill in the required inputs, and run queries. Results are displayed in real-time with detailed analysis."
  },
  {
    question: "How do I connect to my AMS system?",
    answer: "In the Document Retrieval workflow, you can select your AMS system (Applied Epic, AMS360, HawkSoft, etc.) to retrieve policy documents. The platform integrates with major agency management systems for seamless document access."
  },
  {
    question: "Is my data secure?",
    answer: "Yes! Fideon OS runs on private, secure infrastructure. Your data is encrypted in transit and at rest. AI models can run locally on your devices for maximum privacy, or you can use cloud sync for enhanced performance while maintaining enterprise-grade security."
  },
  {
    question: "What does the Pod Dashboard show?",
    answer: "The Pod Dashboard displays real-time metrics for each active pod including query count, success rate, average response time, and recent activity. Click on any pod card to view detailed analytics and usage history."
  },
];

export function FAQSection() {
  return (
    <Card className="bg-card/80 backdrop-blur-sm border-border/50 shadow-card overflow-hidden">
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-accent/5 opacity-50" />
      <CardHeader className="relative pb-3">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-primary/10 to-primary/5">
            <HelpCircle className="h-5 w-5 text-primary" />
          </div>
          <div>
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <FideonLogo size={18} />
              Fideon Help Center
            </CardTitle>
            <CardDescription>Frequently asked questions about the platform</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="relative">
        <Accordion type="single" collapsible className="w-full">
          {faqs.map((faq, index) => (
            <AccordionItem key={index} value={`item-${index}`} className="border-border/50">
              <AccordionTrigger className="text-sm text-left hover:text-primary hover:no-underline py-3">
                {faq.question}
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground pb-3">
                {faq.answer}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </CardContent>
    </Card>
  );
}
