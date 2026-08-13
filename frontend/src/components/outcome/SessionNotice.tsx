"use client";

import { Alert } from "@/components/ui/alert";
import { type SessionInfo } from "@/services/endpoints";

/**
 * Çoklu karşılaştırma muhasebesi.
 *
 * 20 şekil denenirse %95 güvenle ~1 tanesinin şans eseri "anlamlı" çıkması
 * beklenir. Sayaç ve düzeltilmiş α kullanıcıdan saklanmaz.
 */
export function SessionNotice({ session }: { session: SessionInfo | null }) {
  if (!session) return null;

  if (!session.multiple_comparison_warning) {
    return (
      <p className="px-1 text-[11px] text-muted-foreground">
        Bu oturumda {session.session_queries} şekil denendi.
      </p>
    );
  }

  return (
    <Alert tone="warn" title={`Bu oturumda ${session.session_queries} şekil denendi`}>
      {session.warning_text ??
        `Bonferroni düzeltilmiş α = ${session.adjusted_alpha.toFixed(4)}.`}
    </Alert>
  );
}
