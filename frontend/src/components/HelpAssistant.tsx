import { useState, useRef, useEffect } from "react";
import { Brain, Send, Sparkles, Loader2, MessageSquare, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const QUICK_PROMPTS = [
  { label: "What is Fideon Fabric?", icon: Brain },
  { label: "How do I activate a pod?", icon: Sparkles },
  { label: "What's the Playground?", icon: MessageSquare },
  { label: "Is my data secure?", icon: ArrowRight },
];

export function HelpAssistant() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMessage = async (messageText: string) => {
    if (!messageText.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: messageText };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    let assistantContent = "";

    try {
      const CHAT_URL = `${process.env.NEXT_PUBLIC_API_URL}/api/help-assistant`;
      
      const { data: { session } } = await supabase.auth.getSession();
      
      const resp = await fetch(CHAT_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.access_token || process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY}`,
        },
        body: JSON.stringify({
          messages: [...messages, userMessage].map(m => ({ role: m.role, content: m.content })),
        }),
      });

      if (!resp.ok) {
        if (resp.status === 429) {
          toast({ title: "Rate limit exceeded", description: "Please try again in a moment.", variant: "destructive" });
          throw new Error("Rate limited");
        }
        if (resp.status === 402) {
          toast({ title: "Credits required", description: "Please add credits to continue.", variant: "destructive" });
          throw new Error("Payment required");
        }
        throw new Error("Failed to get response");
      }

      const reader = resp.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let textBuffer = "";

      // Add empty assistant message to update
      setMessages(prev => [...prev, { role: "assistant", content: "" }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        textBuffer += decoder.decode(value, { stream: true });

        let newlineIndex: number;
        while ((newlineIndex = textBuffer.indexOf("\n")) !== -1) {
          let line = textBuffer.slice(0, newlineIndex);
          textBuffer = textBuffer.slice(newlineIndex + 1);

          if (line.endsWith("\r")) line = line.slice(0, -1);
          if (line.startsWith(":") || line.trim() === "") continue;
          if (!line.startsWith("data: ")) continue;

          const jsonStr = line.slice(6).trim();
          if (jsonStr === "[DONE]") break;

          try {
            const parsed = JSON.parse(jsonStr);
            const content = parsed.choices?.[0]?.delta?.content as string | undefined;
            if (content) {
              assistantContent += content;
              setMessages(prev => {
                const updated = [...prev];
                updated[updated.length - 1] = { role: "assistant", content: assistantContent };
                return updated;
              });
            }
          } catch {
            textBuffer = line + "\n" + textBuffer;
            break;
          }
        }
      }
    } catch (error) {
      console.error("Help assistant error:", error);
      if (!assistantContent) {
        setMessages(prev => prev.filter(m => m.content !== ""));
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <div className="p-1.5 rounded-lg bg-primary/10 relative">
          <Brain className="h-4 w-4 text-primary" />
          <span className="absolute -top-0.5 -right-0.5 h-2 w-2 bg-emerald-500 rounded-full animate-pulse" />
        </div>
        <div>
          <p className="text-sm font-semibold text-sidebar-foreground flex items-center gap-1.5">
            <Sparkles className="h-3 w-3 text-primary" />
            Fideon Assistant
          </p>
          <p className="text-[10px] text-sidebar-foreground/60">Ask me anything</p>
        </div>
      </div>

      {/* Chat Messages */}
      {messages.length > 0 && (
        <ScrollArea className="h-[180px] pr-2" ref={scrollRef}>
          <div className="space-y-2">
            {messages.map((message, index) => (
              <div
                key={index}
                className={cn(
                  "flex gap-1.5",
                  message.role === "user" ? "justify-end" : "justify-start"
                )}
              >
                {message.role === "assistant" && (
                  <div className="h-5 w-5 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Brain className="h-3 w-3 text-primary" />
                  </div>
                )}
                <div
                  className={cn(
                    "rounded-md px-2.5 py-1.5 max-w-[90%] text-xs leading-relaxed",
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-sidebar-accent/50 text-sidebar-foreground"
                  )}
                >
                  {message.content || (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  )}
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      )}

      {/* Quick Prompts */}
      {messages.length === 0 && (
        <div className="grid grid-cols-1 gap-1.5">
          {QUICK_PROMPTS.map((prompt) => (
            <button
              key={prompt.label}
              onClick={() => sendMessage(prompt.label)}
              disabled={isLoading}
              className="flex items-center gap-2 px-2.5 py-2 rounded-md border border-sidebar-border/50 bg-sidebar-accent/30 hover:bg-sidebar-accent/60 hover:border-primary/30 transition-all text-left text-xs text-sidebar-foreground/70 hover:text-sidebar-foreground group"
            >
              <prompt.icon className="h-3.5 w-3.5 text-primary/70 group-hover:text-primary transition-colors flex-shrink-0" />
              <span className="truncate">{prompt.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="flex gap-1.5">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about Fideon Fabric..."
          disabled={isLoading}
          className="flex-1 h-8 text-xs bg-sidebar-accent/30 border-sidebar-border/50 focus:border-primary/50"
        />
        <Button
          type="submit"
          size="icon"
          disabled={!input.trim() || isLoading}
          className="shrink-0 h-8 w-8"
        >
          {isLoading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Send className="h-3.5 w-3.5" />
          )}
        </Button>
      </form>

      {/* Reset Chat */}
      {messages.length > 0 && (
        <button
          onClick={() => setMessages([])}
          className="text-[10px] text-sidebar-foreground/50 hover:text-sidebar-foreground transition-colors"
        >
          Clear conversation
        </button>
      )}
    </div>
  );
}
