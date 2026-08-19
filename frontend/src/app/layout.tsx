import type { ReactNode } from "react";

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
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
