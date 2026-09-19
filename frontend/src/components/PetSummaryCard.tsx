/**
 * Pet summary card shown at the top of the dashboard.
 *
 * At-a-glance answers to the two questions every pet owner has when they
 * open the app:
 *
 *   1. *Who* is this — photo / species emoji, breed, age, current weight
 *   2. *How is the pet* — when was the last feeding and the last weight?
 *
 * The card links "add" buttons into the QuickAdd flow so the user can
 * act on the empty slots without leaving the dashboard.
 */

import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Card, Skeleton } from 'antd-mobile';
import { AddOutline } from 'antd-mobile-icons';

import { petsService, type Pet } from '../services/pets.service';
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
        background: "none",
        border: "none",
        padding: "8px 12px",
        borderRadius: "10px",
        cursor: "pointer",
      }}
    >
      <div style={{ fontSize: "11px", color: "var(--app-text-secondary)", textTransform: "uppercase", letterSpacing: "0.4px", fontWeight: 600 }}>
        {label}
      </div>
      <div style={{ marginTop: "2px", fontSize: "14px", color: "var(--app-text-color)", fontWeight: 600 }}>
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
  const subtitleParts = [
    pet.breed,
    pet.gender,
    age ? `${age}` : null,
  ].filter(Boolean);

  return (
    <Card
      style={{
        borderRadius: "16px",
        border: "none",
        boxShadow: "var(--app-shadow)",
        marginBottom: "var(--spacing-md)",
      }}
    >
      <div style={{ padding: "16px" }}>
        {/* Identity row */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div
            style={{
              width: "56px",
              height: "56px",
              borderRadius: "50%",
              backgroundColor: "var(--app-page-background)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "32px",
              flexShrink: 0,
              overflow: "hidden",
            }}
          >
            {pet.photo_url ? (
              <PetImage src={pet.photo_url} alt={pet.name} />
            ) : (
              <span aria-hidden>{speciesEmoji(pet.species)}</span>
            )}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: "6px", flexWrap: "wrap" }}>
              <span style={{ fontSize: "20px", fontWeight: 700, color: "var(--app-text-color)" }}>
                {pet.name}
              </span>
              {pet.species && (
                <span style={{ fontSize: "13px", color: "var(--app-text-secondary)" }}>
                  {speciesEmoji(pet.species)} {pet.species}
                </span>
              )}
            </div>
            {subtitleParts.length > 0 && (
              <div style={{ marginTop: "2px", fontSize: "13px", color: "var(--app-text-secondary)" }}>
                {subtitleParts.join(" · ")}
              </div>
            )}
          </div>
          <AddOutline
            style={{ fontSize: "20px", color: "var(--app-text-secondary)" }}
            onClick={() => onQuickAdd("feeding")}
          />
        </div>

        {/* At-a-glance: last feeding + last weight */}
        <div
          style={{
            marginTop: "12px",
            display: "flex",
            background: "var(--app-page-background)",
            borderRadius: "10px",
            gap: "4px",
          }}
        >
          <LastEvent
            label="Кормление"
            dateTime={lastFeedingDateTime}
            emptyLabel="не записано"
            addPath="/form/feeding"
            onAdd={() => onQuickAdd("feeding")}
          />
          <div style={{ width: "1px", backgroundColor: "var(--app-border-color)", margin: "8px 0" }} />
          <LastEvent
            label={lastWeightRecord ? `Вес ${lastWeightRecord.weight} кг` : "Вес"}
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
    </Card>
  );
}