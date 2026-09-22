/**
 * Pet summary card shown at the top of the dashboard.
 *
 * Side-by-side layout: a square avatar (or species icon when no photo)
 * on the left, the pet's name and quick meta on the right. Below the
 * header row sit the last-event chips (кормление / вес) so the user
 * can jump into the timeline in one tap.
 */

import { useQuery } from '@tanstack/react-query';
import { createElement } from 'react';
import { useNavigate } from 'react-router-dom';
import { Scale } from 'lucide-react';
import { Skeleton } from 'antd-mobile';

import { type LucideIcon } from 'lucide-react';
import { type Pet } from '../services/pets.service';
import { healthRecordsService } from '../services/healthRecords.service';
import { computePetAge, formatRelativeShort } from '../utils/relativeTime';
import { hapticFeedback } from '../utils/haptic';
import { speciesIconMap, SPECIES_FALLBACK_ICON, genderLabel } from '../utils/constants';
import { PetImage } from './PetImage';
import { CountUp } from './CountUp';


function speciesIcon(species?: string): LucideIcon {
  if (!species) return SPECIES_FALLBACK_ICON;
  const key = species.toLowerCase().trim();
  return speciesIconMap[key] ?? SPECIES_FALLBACK_ICON;
}


interface LastEventProps {
  label: string;
  dateTime: string | undefined;
  emptyLabel: string;
  addPath: string;
  onAdd: () => void;
}


function LastEvent({ label, dateTime, emptyLabel, addPath, onAdd }: LastEventProps) {
  const navigate = useNavigate();
  return (
    <button
      type="button"
      onClick={() => {
        hapticFeedback("light");
        if (dateTime) {
          navigate("/history");
        } else {
          onAdd();
          navigate(addPath);
        }
      }}
      style={{
        flex: 1,
        minWidth: 0,
        textAlign: "left",
        background: "var(--app-accent-soft)",
        border: "none",
        padding: "10px 12px",
        borderRadius: "12px",
        cursor: "pointer",
        display: "flex",
        flexDirection: "column",
        gap: "2px",
      }}
    >
      <div style={{
        fontSize: "10px",
        color: "var(--app-accent-deep)",
        textTransform: "uppercase",
        letterSpacing: "0.4px",
        fontWeight: 600,
      }}>
        {label}
      </div>
      <div style={{
        fontSize: "13px",
        color: "var(--app-text-primary)",
        fontWeight: 600,
        fontFamily: "var(--font-display)",
      }}>
        {dateTime ? formatRelativeShort(dateTime) : emptyLabel}
      </div>
    </button>
  );
}


export function PetSummaryCard({ pet, onQuickAdd }: { pet: Pet; onQuickAdd: (tileId: string) => void }) {
  // Fetch the most-recent feeding and weight to render "last X" lines.
  const feedings = useQuery({
    queryKey: ["pet-summary", "feeding", pet._id],
    queryFn: () => healthRecordsService.getList("feeding", pet._id, 1, 1),
    enabled: !!pet._id,
    staleTime: 30_000,
  });
  const weights = useQuery({
    queryKey: ["pet-summary", "weight", pet._id],
    queryFn: () => healthRecordsService.getList("weight", pet._id, 1, 1),
    enabled: !!pet._id,
    staleTime: 30_000,
  });

  const lastFeedingDateTime = feedings.data?.items?.[0]?.date_time;
  const lastWeightRecord = weights.data?.items?.[0];

  const age = computePetAge(pet.birth_date ?? "");
  // speciesIcon() selects among a fixed set of icons — see the identical
  // comment in PetImage.tsx for why createElement is used below instead
  // of JSX to render it.
  const SpeciesIcon = speciesIcon(pet.species);

  return (
    <div
      className="card-soft"
      style={{
        overflow: "hidden",
        marginBottom: "var(--spacing-md)",
        padding: "16px",
      }}
    >
      {/* Header row — square avatar on the left, name + meta on the right.
          The avatar slot is fixed-size (112 × 112) so text alignment stays
          consistent across photo / no-photo / long-name cases. */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--spacing-md)",
          marginBottom: "var(--spacing-md)",
        }}
      >
        {/* Square avatar — image if available, else species icon on the
            brand-soft tint. object-fit: cover keeps the photo square
            even if the source is rectangular. */}
        <div
          aria-hidden={!pet.photo_url}
          style={{
            flexShrink: 0,
            width: "112px",
            height: "112px",
            borderRadius: "var(--radius-md)",
            overflow: "hidden",
            backgroundColor: "var(--app-accent-soft)",
            color: "var(--app-accent-deep)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {pet.photo_url ? (
            <PetImage
              src={pet.photo_url}
              alt={pet.name}
              size={112}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                borderRadius: 0,
              }}
            />
          ) : (
            createElement(SpeciesIcon, { size: 56, strokeWidth: 1.6, style: { display: "block" }, "aria-hidden": true })
          )}
        </div>

        {/* Right column — name, age/gender/breed summary, weight chip.
            minWidth: 0 lets flex children ellipsis correctly. */}
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: "6px" }}>
          <div
            className="display-headline"
            style={{
              fontSize: "var(--text-xl)",
              fontWeight: 700,
              color: "var(--app-text-primary)",
              // Long names like «Шерри-Мими» truncate instead of wrapping.
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {pet.name}
          </div>

          {/* Meta line — only render the parts we have */}
          <div
            style={{
              fontSize: "var(--text-sm)",
              color: "var(--app-text-secondary)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {[age, pet.breed, genderLabel(pet.gender)].filter(Boolean).join(", ") || "—"}
          </div>

          {/* Weight chip — the always-relevant health metric */}
          {lastWeightRecord && (
            <span
              className="chip"
              style={{
                alignSelf: "flex-start",
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                fontSize: "12px",
                // A full pill next to the avatar's soft rounded-square
                // photo read as two different shape languages in the
                // same card — this matches the avatar's corner instead.
                borderRadius: "var(--radius-sm)",
              }}
            >
              <Scale size={13} strokeWidth={2.2} style={{ display: "block" }} />
              <CountUp to={lastWeightRecord.fields?.weight as number} duration={800} decimals={1} /> кг
            </span>
          )}
        </div>
      </div>

      {/* Last-event row — Кормление + Вес */}
      <div
        style={{
          display: "flex",
          gap: "8px",
        }}
      >
        <LastEvent
          label="Кормление"
          dateTime={lastFeedingDateTime}
          emptyLabel="не записано"
          addPath="/form/feeding"
          onAdd={() => onQuickAdd("feeding")}
        />
        <LastEvent
          label="Вес"
          dateTime={lastWeightRecord?.date_time}
          emptyLabel="не записан"
          addPath="/form/weight"
          onAdd={() => onQuickAdd("weight")}
        />
      </div>

      {feedings.isLoading || weights.isLoading ? (
        <Skeleton.Paragraph lineCount={1} style={{ marginTop: "12px" }} />
      ) : null}
    </div>
  );
}