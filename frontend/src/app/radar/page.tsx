import { SearchWorkspace } from "@/components/workspace/SearchWorkspace";

export const metadata = {
  title: "Radar — GraphFlow",
  description: "Şu anda oluşmakta olan formasyonları tarayın.",
};

export default function RadarPage() {
  return (
    <SearchWorkspace
      mode="live"
      title="Canlı radar"
      description="Her sembolün en son penceresi taranır. Oluşmakta olan (kapanmamış) mum veriden düşülür."
      submitLabel="Piyasayı tara"
    />
  );
}
