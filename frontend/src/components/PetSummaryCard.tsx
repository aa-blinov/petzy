/**
 * Pet summary card shown at the top of the dashboard.
 *
 * Designed in the "warm pet-care" style — a full-bleed photo hero with the
 * pet's name overlaid, meta chips underneath, and last-event chips at the
 * bottom. Inspired by Pawza's "pet profile" treatment.
 */

import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Scale } from 'lucide-react';
import { Skeleton } from 'antd-mobile';

import { type LucideIcon } from 'lucide-react';
import { type Pet } from '../services/pets.service';
import { healthRecordsService } from '../services/healthRecords.service';
import { computePetAge, formatRelativeShort } from '../utils/relativeTime';
import { hapticFeedback } from '../utils/haptic';
import { speciesIconMap, SPECIES_FALLBACK_ICON } from '../utils/constants';
import { useScrollParallax } from '../hooks/useScrollParallax';
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

  const lastFeedingDateTime = feedings.data?.feedings?.[0]?.date_time;
  const lastWeightRecord = weights.data?.weights?.[0];

  const age = computePetAge(pet.birth_date ?? "");
  const SpeciesIcon = speciesIcon(pet.species);
  const parallaxTransform = useScrollParallax(0.15);

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
        className="parallax-hero"
        style={{
          position: "relative",
          width: "100%",
          height: "180px",
          backgroundColor: "var(--tile-brown)",
          overflow: "hidden",
        }}
      >
        {pet.photo_url ? (
          <div style={{ position: 'absolute', inset: 0, transform: parallaxTransform }}>
            <PetImage
              src={pet.photo_url}
              alt={pet.name}
              size={180}
              style={{ width: "100%", height: "100%", borderRadius: 0 }}
            />
          </div>
        ) : (
          <div
            aria-hidden
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#FFFFFF",
              opacity: 0.9,
              transform: parallaxTransform,
            }}
          >
            <SpeciesIcon size={84} strokeWidth={1.5} style={{ display: 'block' }} />
          </div>
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

        {/* Pet name overlay — only the name + age (if known).
           Species is conveyed by the emoji, no need to repeat it as text. */}
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
          {age && (
            <div
              style={{
                marginTop: "2px",
                fontSize: "13px",
                opacity: 0.92,
              }}
            >
              {age}
            </div>
          )}
        </div>
      </div>

      {/* Meta chips — only render if we have something to show. Breed and gender
           appear here when set, weight is the always-relevant one. */}
      {(pet.breed || pet.gender || lastWeightRecord) && (
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
            <span className="chip">
              <Scale size={14} strokeWidth={2.2} style={{ display: 'block' }} />
              <CountUp to={lastWeightRecord.weight} duration={800} decimals={1} /> кг
            </span>
          )}
        </div>
      )}

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
