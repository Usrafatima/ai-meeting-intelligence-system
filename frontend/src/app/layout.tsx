import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "AI Meeting Intelligence System",
  description: "AI-powered web application for meeting intelligence and analysis",
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html lang="en" className="scroll-smooth">
      <body>{children}</body>
    </html>
  );
}