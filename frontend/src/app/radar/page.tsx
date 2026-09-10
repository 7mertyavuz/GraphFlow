import { SearchWorkspace } from "@/components/workspace/SearchWorkspace";

export const metadata = {
  title: "Radar — GraphFlow",
  description: "Scan the patterns forming right now · Şu anda oluşmakta olan formasyonları tarayın.",
};

export default function RadarPage() {
  return (
    <SearchWorkspace
      mode="live"
      copy="radar"
    />
  );
}
