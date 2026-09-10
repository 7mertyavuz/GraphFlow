"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FlaskConical, LineChart, Radar } from "lucide-react";

import { useHealth } from "@/hooks/useGraphFlowApi";
import { useI18n } from "@/i18n/LanguageProvider";
import { LANGS } from "@/i18n/messages";
import { cn } from "@/lib/utils";
import { formatRelative } from "@/utils/formatters";

export function Header() {
  const pathname = usePathname();
  const { t } = useI18n();
  const links = [
    { href: "/radar", label: t.nav.radar, icon: Radar },
    { href: "/backtest", label: t.nav.backtest, icon: LineChart },
    { href: "/bulgular", label: t.nav.findings, icon: FlaskConical },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/70 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-[1600px] items-center justify-between gap-4 px-4 lg:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2">
          <Logo />
          <span className="text-sm font-semibold tracking-tight">GraphFlow</span>
        </Link>

        <nav className="flex items-center gap-1">
          {links.map((link) => {
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

        <div className="flex shrink-0 items-center gap-3">
          <DataStatus />
          <LanguageToggle />
        </div>
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

/** TR / EN — seçim tarayıcıda saklanır; ilk açılışta tarayıcı dili. */
function LanguageToggle() {
  const { lang, setLang, t } = useI18n();
  return (
    <div
      role="radiogroup"
      aria-label={t.lang.aria}
      className="flex items-center rounded-lg border border-border p-0.5 text-[11px] font-medium"
    >
      {LANGS.map((code) => (
        <button
          key={code}
          type="button"
          role="radio"
          aria-checked={lang === code}
          onClick={() => setLang(code)}
          className={cn(
            "rounded-md px-2 py-0.5 uppercase transition-colors",
            lang === code
              ? "bg-secondary text-foreground"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {code}
        </button>
      ))}
    </div>
  );
}

/** Veri tazeliği başlıkta durur: bayat veri sessizce sunulmaz. */
function DataStatus() {
  const { data, isLoading, isError } = useHealth();
  const { t } = useI18n();

  const state = isError
    ? { tone: "bg-down", label: t.status.apiDown }
    : isLoading
      ? { tone: "bg-muted-foreground", label: t.status.connecting }
      : data?.stale_warning
        ? { tone: "bg-warp", label: t.status.data(formatRelative(data.data_as_of)) }
        : { tone: "bg-up", label: t.status.data(formatRelative(data?.data_as_of)) };

  return (
    <div
      className="hidden shrink-0 items-center gap-2 text-[11px] text-muted-foreground sm:flex"
      title={data?.stale_warning ? t.status.staleTitle : t.status.freshTitle}
    >
      <span className={cn("size-1.5 rounded-full", state.tone)} />
      <span className="tabular">{state.label}</span>
    </div>
  );
}
