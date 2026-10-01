/**
 * Pet summary card shown at the top of the dashboard.
 *
 * Side-by-side layout: a square avatar (or species icon when no photo)
 * on the left, the pet's name, quick meta and the last weight on the right.
 * The medical card has its own tab, so no way into it here. The last feeding and weight used to
 * be two tiles here: the feed under the card already shows them, so the card
 * stays a card of the pet.
 */

import { useQuery } from '@tanstack/react-query';
import { createElement, useState, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Scale } from 'lucide-react';
import { PhotoViewer } from './PhotoViewer';

import { type Pet } from '../services/pets.service';
import { healthRecordsService } from '../services/healthRecords.service';
import { computePetAge } from '../utils/relativeTime';
import { genderLabel } from '../utils/constants';
import { getSpecies, speciesLabel } from '../utils/species';
import { useAuth } from '../hooks/useAuth';
import { PetImage } from './PetImage';
import { CountUp } from './CountUp';




export function PetSummaryCard({ pet }: { pet: Pet }) {
  // Fetch the most-recent feeding and weight to render "last X" lines.
  const weights = useQuery({
    queryKey: ["pet-summary", "weight", pet._id],
    queryFn: () => healthRecordsService.getList("weight", pet._id, 1, 1),
    enabled: !!pet._id,
    staleTime: 30_000,
  });

  const lastWeightRecord = weights.data?.items?.[0];

  const age = computePetAge(pet.birth_date ?? "");
  const meta = [age, pet.breed, genderLabel(pet.gender)].filter(Boolean).join(", ");
  const { username } = useAuth();
  const navigate = useNavigate();
  // The photo opens at full size; a pet with no photo has a picture of its species there, nothing to enlarge.
  const [photoOpen, setPhotoOpen] = useState(false);
  // Nothing known yet: the owner (only they can edit the pet) is asked to
  // fill it in; someone it's shared with sees at least what animal it is.
  const canFillIn = !meta && (pet.current_user_is_owner ?? pet.owner === username);
  // A fixed set of module-level icons — see the identical comment in
  // PetImage.tsx for why createElement is used below instead of JSX.
  const SpeciesIcon = getSpecies(pet.species).icon;

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
          {...(pet.photo_url
            ? {
                role: "button",
                tabIndex: 0,
                "aria-label": `Открыть фото: ${pet.name}`,
                className: "tap-feedback",
                onClick: () => setPhotoOpen(true),
                onKeyDown: (event: KeyboardEvent<HTMLDivElement>) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setPhotoOpen(true);
                  }
                },
              }
            : {})}
          style={{
            flexShrink: 0,
            width: "112px",
            height: "112px",
            cursor: pet.photo_url ? "pointer" : "default",
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
              priority
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

          {/* Meta line — only render the parts we have. Wraps instead of
              truncating: age + breed + gender together routinely overrun
              one line on a phone-width card, and unlike the name above,
              losing the tail of this line loses actual information
              (which breed) rather than just a stylistic flourish.
              Lowercased for display only — breed and gender aren't proper
              nouns in Russian, so mid-sentence capitals (from the stored
              breed text and genderLabel()) read as an artifact here.
              Doesn't touch the underlying data or other screens. */}
          {/* Three lines at most: an ordinary breed still reads whole, a
              100-character one no longer pushes the card to six lines. */}
          <div
            className="clamp-3"
            style={{
              fontSize: "var(--text-sm)",
              color: "var(--app-text-secondary)",
              textTransform: "lowercase",
            }}
          >
            {meta || (!canFillIn && speciesLabel(pet.species))}
          </div>
          {canFillIn && (
            <button
              type="button"
              className="touch-target"
              onClick={() => navigate(`/pets/${pet._id}/edit`)}
              style={{
                alignSelf: "flex-start",
                marginTop: "-4px",
                padding: 0,
                border: "none",
                background: "none",
                font: "inherit",
                fontSize: "var(--text-sm)",
                fontWeight: 600,
                color: "var(--app-accent-deep)",
                cursor: "pointer",
              }}
            >
              Добавить возраст и породу
            </button>
          )}

          {/* The weight, the always-relevant health metric. The medical card is its own row
              below: next to this chip it looked like one more figure, not a way in. */}
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

      {pet.photo_url && <PhotoViewer image={pet.photo_url} visible={photoOpen} onClose={() => setPhotoOpen(false)} />}
    </div>
  );
}