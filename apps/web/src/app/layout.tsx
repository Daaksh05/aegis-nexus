import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { SiteNav } from "../components/site-nav";

export const metadata: Metadata = {
  title: "Aegis Nexus",
  description: "Public-transport resilience digital twin.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <SiteNav />
        <main className="page-content">{children}</main>
        <footer className="site-footer">
          <div className="footer-inner">
            <Link href="/status">Status</Link>
          </div>
        </footer>
      </body>
    </html>
  );
}
