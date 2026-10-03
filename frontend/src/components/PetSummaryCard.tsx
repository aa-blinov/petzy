/**
 * Pet summary card shown at the top of the dashboard.
 *
 * Side-by-side layout: a square avatar (or species icon when no photo)
 * on the left, the pet's name and quick meta on the right.
 * The medical card has its own tab, so no way into it here. The last feeding and weight used to
 * be here: the feed under the card already shows them (and the weight is a slow figure with its own chart, not
 * something to act on), so the card stays a card of who the pet is.
 */

import { createElement, useEffect, useState, type KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { PhotoViewer } from './PhotoViewer';

import { type Pet } from '../services/pets.service';
import { computePetAge } from '../utils/relativeTime';
import { genderLabel } from '../utils/constants';
import { getSpecies, speciesLabel } from '../utils/species';
import { useAuth } from '../hooks/useAuth';
import { PetImage } from './PetImage';
import { loadPetFont, petAccentAttr, petFontOf, petFontStyle, petFrameStyle, petLookOf, type PetLook } from '../utils/petLook';




/** `look` shows a draft in place of the saved one: the settings page previews it on this same card. */
export function PetSummaryCard({ pet, look: lookOverride }: { pet: Pet; look?: PetLook }) {
  const look = lookOverride ?? petLookOf(pet);
  const accentAttr = petAccentAttr(look);
  const font = petFontOf(look);
  const frame = petFrameStyle(look.frame);
  useEffect(() => {
    if (font) void loadPetFont(font);
  }, [font]);
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
      {...accentAttr}
      style={{
        overflow: "hidden",
        marginBottom: "var(--spacing-md)",
        padding: "16px",
        // A chosen colour tints the whole card (a photo pet has no tinted avatar to show it); none keeps the plain card.
        ...(accentAttr["data-pet-accent"]
          ? { background: "color-mix(in srgb, var(--app-accent-soft) 60%, var(--app-card-background))" }
          : {}),
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
            ...frame.box,
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
                ...frame.image,
              }}
            />
          ) : (
            createElement(SpeciesIcon, { size: 56, strokeWidth: 1.6, style: { display: "block" }, "aria-hidden": true })
          )}
        </div>

        {/* Right column — name and the age, breed and gender line.
            minWidth: 0 lets flex children ellipsis correctly. */}
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: "6px" }}>
          <div
            className="display-headline"
            style={{
              fontSize: "var(--text-xl)",
              fontWeight: 700,
              color: "var(--app-text-primary)",
              // Two lines before a cut: a long name is still a name.
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
              overflowWrap: "anywhere",
              ...petFontStyle(font, "var(--text-xl)"),
            }}
          >
            {pet.name}
          </div>

          {/* The line the family put under the name; the pet's own colour reaches the avatar tint and this line. */}
          {look.tagline && (
            <div
              style={{
                fontSize: "var(--text-sm)",
                fontWeight: 600,
                color: "var(--app-accent-deep)",
                overflowWrap: "anywhere",
              }}
            >
              {look.tagline}
            </div>
          )}

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
        </div>
      </div>

      {pet.photo_url && <PhotoViewer image={pet.photo_url} visible={photoOpen} onClose={() => setPhotoOpen(false)} />}
    </div>
  );
}