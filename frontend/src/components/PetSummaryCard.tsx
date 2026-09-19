/**
 * Pet summary card shown at the top of the dashboard.
 *
 * Designed in the "warm pet-care" style — a full-bleed photo hero with the
 * pet's name overlaid, meta chips underneath, and last-event chips at the
 * bottom. Inspired by Pawza's "pet profile" treatment.
 */

import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Skeleton } from 'antd-mobile';

import { type Pet } from '../services/pets.service';
import { healthRecordsService } from '../services/healthRecords.service';
import { computePetAge, formatRelativeShort } from '../utils/relativeTime';
import { hapticFeedback } from '../utils/haptic';
import { PetImage } from './PetImage';


const SPECIES_EMOJI: Record<string, string> = {
  cat: "🐱",
  dog: "🐶",
  bird: "🐦",
  rabbit: "🐰",
  hamster: "🐹",
  fish: "🐟",
  reptile: "🦎",
  other: "🐾",
};


function speciesEmoji(species?: string): string {
  if (!species) return SPECIES_EMOJI.other;
  const key = species.toLowerCase().trim();
  return SPECIES_EMOJI[key] ?? SPECIES_EMOJI.other;
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

  const lastFeedingDateTime = feedings.data?.feedings?.[0]?.date_time;
  const lastWeightRecord = weights.data?.weights?.[0];

  const age = computePetAge(pet.birth_date ?? "");
  const species = speciesEmoji(pet.species);

  return (
    <div
      className="card-soft"
      style={{
        overflow: "hidden",
        marginBottom: "var(--spacing-md)",
      }}
    >
      {/* Hero photo */}
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "180px",
          backgroundColor: "var(--tile-brown)",
          overflow: "hidden",
        }}
      >
        {pet.photo_url ? (
          <PetImage
            src={pet.photo_url}
            alt={pet.name}
            size={180}
            style={{ width: "100%", height: "100%", borderRadius: 0 }}
          />
        ) : (
          <span
            aria-hidden
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "84px",
              opacity: 0.85,
            }}
          >
            {species}
          </span>
        )}

        {/* Bottom gradient for legibility */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "linear-gradient(180deg, rgba(0,0,0,0) 40%, rgba(31,27,22,0.55) 100%)",
            pointerEvents: "none",
          }}
        />

        {/* Pet name overlay */}
        <div
          style={{
            position: "absolute",
            left: "16px",
            right: "16px",
            bottom: "14px",
            color: "#FFFFFF",
          }}
        >
          <div
            className="display-headline"
            style={{
              fontSize: "28px",
              fontWeight: 700,
              textShadow: "0 1px 2px rgba(0,0,0,0.25)",
            }}
          >
            {pet.name}
          </div>
          {pet.species && (
            <div
              style={{
                marginTop: "2px",
                fontSize: "13px",
                opacity: 0.92,
                display: "flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              <span>{pet.species}</span>
              {age ? (
                <>
                  <span style={{ opacity: 0.6 }}>·</span>
                  <span>{age}</span>
                </>
              ) : null}
            </div>
          )}
        </div>
      </div>

      {/* Meta chips */}
      <div
        style={{
          padding: "14px 16px 12px",
          display: "flex",
          flexWrap: "wrap",
          gap: "6px",
        }}
      >
        {pet.breed && <span className="chip">{pet.breed}</span>}
        {pet.gender && <span className="chip">{pet.gender}</span>}
        {lastWeightRecord && (
          <span className="chip">⚖️ {lastWeightRecord.weight} кг</span>
        )}
      </div>

      {/* Last-event chips */}
      <div
        style={{
          padding: "0 16px 16px",
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
          label={lastWeightRecord ? "Вес" : "Вес"}
          dateTime={lastWeightRecord?.date_time}
          emptyLabel="не записан"
          addPath="/form/weight"
          onAdd={() => onQuickAdd("weight")}
        />
      </div>

      {feedings.isLoading || weights.isLoading ? (
        <Skeleton.Paragraph lineCount={1} style={{ marginTop: "12px", padding: "0 16px 12px" }} />
      ) : null}
    </div>
  );
}
