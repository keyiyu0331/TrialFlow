import type { DelayLevel, SiteHealth, SourceType } from "@/lib/api";
import { DELAY_SHORT, HEALTH_LABEL } from "@/lib/format";

export function HealthChip({ health }: { health: SiteHealth }) {
  return <span className={`chip chip--${health}`}>{HEALTH_LABEL[health]}</span>;
}

export function DelayChip({ level }: { level: DelayLevel }) {
  return <span className={`chip chip--${level}`}>{DELAY_SHORT[level]}</span>;
}

/** Real = from ClinicalTrials.gov; synthetic = generated demo activation data. */
export function SourceTag({ source, what }: { source: SourceType; what?: string }) {
  const real = source === "public_registry";
  return (
    <span className={`tag ${real ? "tag--real" : ""}`} title={real ? "From ClinicalTrials.gov" : "Synthetic demo data"}>
      {what ? `${what} · ` : ""}
      {real ? "Registry" : "Synthetic"}
    </span>
  );
}
