import fideonLogo from "@/assets/fideon-logo.png";

interface FideonLogoProps {
  className?: string;
  size?: number;
}

export function FideonLogo({ className = "", size = 32 }: FideonLogoProps) {
  return (
    <img
      src={fideonLogo.src}
      alt="Fideon"
      width={size}
      height={size}
      className={className}
    />
  );
}
