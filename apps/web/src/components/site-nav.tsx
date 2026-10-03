"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navigationItems = [
  { href: "/twin", label: "Twin" },
  { href: "/scenarios", label: "Scenarios" },
  { href: "/results", label: "Results" },
  { href: "/copilot", label: "Copilot" },
] as const;

export function SiteNav() {
  const pathname = usePathname() ?? "";

  return (
    <header className="site-header">
      <div className="header-inner">
        <Link className="wordmark" href="/twin">
          Aegis Nexus
        </Link>
        <nav className="primary-nav" aria-label="Primary navigation">
          {navigationItems.map(({ href, label }) => (
            <Link
              className="nav-link"
              href={href}
              aria-current={pathname === href ? "page" : undefined}
              key={href}
            >
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
