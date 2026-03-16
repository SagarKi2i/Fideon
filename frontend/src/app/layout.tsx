import type { Metadata } from "next";
import "../index.css";

export const metadata: Metadata = {
  title: "Fideon OS",
  description: "Fideon OS Next.js migration",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
