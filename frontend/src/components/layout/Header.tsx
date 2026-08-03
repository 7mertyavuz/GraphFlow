"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Radar, LineChart, Activity } from "lucide-react";

const links = [
  { href: "/radar", label: "Radar", icon: Radar },
  { href: "/backtest", label: "Backtest", icon: LineChart },
];

export function Header() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur">
      <div className="flex h-14 items-center justify-between px-4 lg:px-6">
        <Link href="/" className="flex items-center gap-2 font-bold tracking-tight">
          <Activity className="size-5 text-primary" />
          <span>GraphFlow</span>
        </Link>
        <nav className="flex items-center gap-1">
          {links.map((link) => {
            const Icon = link.icon;
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                <Icon className="size-4" />
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
