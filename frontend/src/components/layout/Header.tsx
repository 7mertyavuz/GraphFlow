"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FlaskConical, LineChart, Radar } from "lucide-react";

import { useHealth } from "@/hooks/useGraphFlowApi";
import { cn } from "@/lib/utils";
import { formatRelative } from "@/utils/formatters";

const LINKS = [
  { href: "/radar", label: "Radar", icon: Radar },
  { href: "/backtest", label: "Backtest", icon: LineChart },
  { href: "/bulgular", label: "Bulgular", icon: FlaskConical },
];

export function Header() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/70 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-[1600px] items-center justify-between gap-4 px-4 lg:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2">
          <Logo />
          <span className="text-sm font-semibold tracking-tight">GraphFlow</span>
        </Link>

        <nav className="flex items-center gap-1">
          {LINKS.map((link) => {
            const Icon = link.icon;
            const active = pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                )}
              >
                <Icon className="size-3.5" />
                <span className="hidden sm:inline">{link.label}</span>
              </Link>
            );
          })}
        </nav>

        <DataStatus />
      </div>
    </header>
  );
}

function Logo() {
  return (
    <span className="flex size-7 items-center justify-center rounded-lg border border-brand/30 bg-brand/10">
      <svg viewBox="0 0 24 24" className="size-4" fill="none" aria-hidden>
        <path
          d="M2 17 L7 9 L11 13 L15 5 L22 12"
          className="stroke-brand"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

/** Veri tazeliği başlıkta durur: bayat veri sessizce sunulmaz. */
function DataStatus() {
  const { data, isLoading, isError } = useHealth();

  const state = isError
    ? { tone: "bg-down", label: "API kapalı" }
    : isLoading
      ? { tone: "bg-muted-foreground", label: "bağlanıyor" }
      : data?.stale_warning
        ? { tone: "bg-warp", label: `veri ${formatRelative(data.data_as_of)}` }
        : { tone: "bg-up", label: `veri ${formatRelative(data?.data_as_of)}` };

  return (
    <div
      className="hidden shrink-0 items-center gap-2 text-[11px] text-muted-foreground sm:flex"
      title={
        data?.stale_warning
          ? "Depodaki en yeni bar tazelik sınırının gerisinde — sonuçlar güncel piyasayı yansıtmayabilir."
          : "Depodaki en yeni bar"
      }
    >
      <span className={cn("size-1.5 rounded-full", state.tone)} />
      <span className="tabular">{state.label}</span>
    </div>
  );
}
