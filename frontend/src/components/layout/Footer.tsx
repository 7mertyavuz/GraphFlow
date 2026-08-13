import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-2 px-4 py-5 text-[11px] leading-relaxed text-muted-foreground lg:flex-row lg:items-center lg:justify-between lg:px-6">
        <p className="max-w-3xl">
          GraphFlow sinyal satmaz; ölçülmüş ve dürüstçe raporlanmış geçmiş
          dağılım sunar. Hiçbir başarı oranı baseline olmadan gösterilmez.
          Burada yer alan hiçbir sayı yatırım tavsiyesi değildir.
        </p>
        <Link
          href="/bulgular"
          className="shrink-0 underline underline-offset-4 hover:text-foreground"
        >
          Yöntem ve bulgular →
        </Link>
      </div>
    </footer>
  );
}
