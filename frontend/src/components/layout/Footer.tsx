"use client";

import Link from "next/link";

import { useI18n } from "@/i18n/LanguageProvider";

export function Footer() {
  const { t } = useI18n();
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-2 px-4 py-5 text-[11px] leading-relaxed text-muted-foreground lg:flex-row lg:items-center lg:justify-between lg:px-6">
        <p className="max-w-3xl">{t.footer.body}</p>
        <Link
          href="/bulgular"
          className="shrink-0 underline underline-offset-4 hover:text-foreground"
        >
          {t.footer.link}
        </Link>
      </div>
    </footer>
  );
}
