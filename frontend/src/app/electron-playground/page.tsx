"use client";

import dynamic from "next/dynamic";

const ElectronPlayground = dynamic(
  () => import("@/app-pages/ElectronPlayground"),
  { ssr: false },
);

export default function ElectronPlaygroundPage() {
  return <ElectronPlayground />;
}

