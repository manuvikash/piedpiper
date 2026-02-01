import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PiedPiper - AI Focus Group",
  description: "AI Focus Group Simulation Dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        <nav className="border-b border-zinc-800 bg-zinc-950 px-6 py-3">
          <div className="mx-auto flex max-w-7xl items-center gap-6">
            <Link href="/" className="font-bold text-lg tracking-tight">
              PiedPiper
            </Link>
            <Link
              href="/"
              className="text-sm text-zinc-400 hover:text-zinc-100"
            >
              Dashboard
            </Link>
            <Link
              href="/review"
              className="text-sm text-zinc-400 hover:text-zinc-100"
            >
              Review
            </Link>
          </div>
        </nav>
        <main className="mx-auto max-w-7xl px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
