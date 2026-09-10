"use client";

import { Alert } from "@/components/ui/alert";
import { useI18n } from "@/i18n/LanguageProvider";
import { type SessionInfo } from "@/services/endpoints";

/**
 * Çoklu karşılaştırma muhasebesi.
 *
 * 20 şekil denenirse %95 güvenle ~1 tanesinin şans eseri "anlamlı" çıkması
 * beklenir. Sayaç ve düzeltilmiş α kullanıcıdan saklanmaz.
 */
export function SessionNotice({ session }: { session: SessionInfo | null }) {
  const { t } = useI18n();
  if (!session) return null;

  if (!session.multiple_comparison_warning) {
    return (
      <p className="px-1 text-[11px] text-muted-foreground">
        {t.session.tried(session.session_queries)}
      </p>
    );
  }

  return (
    <Alert tone="warn" title={t.session.triedTitle(session.session_queries)}>
      {/* Metin istemcide üretilir: oturum bilgisi son aramanın yanıtıyla gelir
          ve dil sonradan değişirse sunucunun metni eski dilde kalırdı. */}
      {t.session.warning(session.session_queries, session.adjusted_alpha.toFixed(4))}
    </Alert>
  );
}
