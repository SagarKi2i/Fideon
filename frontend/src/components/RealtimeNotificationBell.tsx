import { Bell } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useRealtimeNotificationInbox } from "@/hooks/useRealtimeNotificationInbox";

function toRelativeTime(iso: string): string {
  const ts = new Date(iso).getTime();
  if (!Number.isFinite(ts)) return "Just now";
  const deltaSec = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (deltaSec < 60) return "Just now";
  if (deltaSec < 3600) return `${Math.floor(deltaSec / 60)}m ago`;
  if (deltaSec < 86400) return `${Math.floor(deltaSec / 3600)}h ago`;
  return `${Math.floor(deltaSec / 86400)}d ago`;
}

export function RealtimeNotificationBell() {
  const navigate = useNavigate();
  const { items, unreadCount, markAllRead, markRead, clearAll } = useRealtimeNotificationInbox();

  const handleNotificationClick = (item: (typeof items)[number]) => {
    markRead(item.id);
    if (item.targetPath) {
      navigate(item.targetPath);
    }
  };
  const getItemClassName = (item: (typeof items)[number]) =>
    `rounded-md border p-2 transition-colors ${
      item.read ? "opacity-70" : "bg-muted/40"
    } ${item.targetPath ? "cursor-pointer hover:bg-muted/60" : ""}`;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="relative h-9 w-9 p-0">
          <Bell className="h-4 w-4" />
          {unreadCount > 0 ? (
            <Badge className="absolute -right-1 -top-1 h-4 min-w-4 px-1 text-[10px] leading-4">
              {unreadCount > 9 ? "9+" : unreadCount}
            </Badge>
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[360px] p-0">
        <div className="flex items-center justify-between border-b px-3 py-2">
          <div className="text-sm font-semibold">Notifications</div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={markAllRead}>
              Mark all read
            </Button>
            <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={clearAll}>
              Clear
            </Button>
          </div>
        </div>
        {items.length === 0 ? (
          <div className="px-3 py-6 text-center text-sm text-muted-foreground">
            No notifications yet.
          </div>
        ) : (
          <ScrollArea className="h-80">
            <div className="space-y-2 p-3">
              {items.map((item: any) => (
                item.targetPath ? (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => handleNotificationClick(item)}
                    className={`${getItemClassName(item)} w-full text-left`}
                  >
                    <div className="text-sm">{item.message}</div>
                    <div className="mt-1 text-[11px] text-muted-foreground">
                      {toRelativeTime(item.createdAt)} - {item.table}
                    </div>
                  </button>
                ) : (
                  <div key={item.id} className={getItemClassName(item)}>
                    <div className="text-sm">{item.message}</div>
                    <div className="mt-1 text-[11px] text-muted-foreground">
                      {toRelativeTime(item.createdAt)} - {item.table}
                    </div>
                  </div>
                )
              ))}
            </div>
          </ScrollArea>
        )}
      </PopoverContent>
    </Popover>
  );
}
