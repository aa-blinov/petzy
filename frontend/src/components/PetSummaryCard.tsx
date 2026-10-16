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
import { PetPhotoFill } from './PetPhotoFill';
import { loadPetFont, petAccentAttr, petFontOf, petFontStyle, petBackdropKey, petBackdropStyle, petCropOf, petFrameStyle, petLookOf, petAccentHex, type PetLook } from '../utils/petLook';




/** `look` shows a draft in place of the saved one: the settings page previews it on this same card. */
export function PetSummaryCard({ pet, look: lookOverride, compact = false }: { pet: Pet; look?: PetLook; compact?: boolean }) {
  // The compact card is the same card in miniature, for a place where it is pinned over something else (the look settings):
  // a smaller picture with its frame scaled to match, the name and the line, no age and breed.
  const slot = compact ? 72 : 112;
  const look = lookOverride ?? petLookOf(pet);
  const accentAttr = petAccentAttr(look);
  const font = petFontOf(look);
  const frame = petFrameStyle(look.frame, slot / 112);
  // A frame cut to a shape (heart, star, cloud…) is a mask: see the box round the avatar below.
  const shapedFrame = Boolean(frame.box.maskImage);
  const backdrop = petBackdropKey(look);
  // The photo backdrop is blurred over the card, so when it arrived late it switched the whole card's tone at once.
  // The picture is loaded first and the backdrop only fades in once it is there, so it never jumps.
  const photoUrl = backdrop === "photo" ? pet.photo_url : undefined;
  const [photoLoaded, setPhotoLoaded] = useState<string | null>(null);
  useEffect(() => {
    if (!photoUrl) return;
    let live = true;
    const img = new Image();
    img.onload = () => { if (live) setPhotoLoaded(photoUrl); };
    img.src = photoUrl;
    return () => { live = false; };
  }, [photoUrl]);
  const photoReady = Boolean(photoUrl) && photoLoaded === photoUrl;
  // The name is hidden until its face has landed: a fallback face at the same size is a different width, and the name
  // jumps when the face comes in. Hidden keeps its place, so nothing moves when it shows.
  // Which face has landed: the key, so a face that is still loading is never taken for a ready one.
  const [landedFont, setLandedFont] = useState<string | null>(null);
  const fontReady = !font || landedFont === font.key;
  useEffect(() => {
    if (!font) return;
    let live = true;
    void loadPetFont(font)
      .then(() => document.fonts?.load(`${font.weight} 1em '${font.family}'`))
      .catch(() => undefined)
      .finally(() => {
        if (live) setLandedFont(font.key);
      });
    return () => {
      live = false;
    };
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
        position: "relative",
        marginBottom: compact ? 0 : "var(--spacing-md)",
        padding: compact ? "12px 16px" : "16px",
        // What lies behind the card: the owner's choice, else a tint of the pet's colour, else the plain card.
        ...petBackdropStyle(backdrop, petAccentHex(look)),
      }}
    >
      {/* The photo itself, blurred and washed out, as the backdrop: a pet with no photo has nothing to blur. */}
      {backdrop === "photo" && pet.photo_url && (
        <div
          aria-hidden
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage: `url(${pet.photo_url})`,
            backgroundSize: "cover",
            backgroundPosition: "center",
            filter: "blur(22px) saturate(1.35)",
            transform: "scale(1.4)",
            opacity: photoReady ? 0.6 : 0,
            transition: "opacity var(--motion-duration-fast) var(--motion-ease-standard)",
          }}
        />
      )}
      {backdrop === "photo" && (
        <div aria-hidden style={{ position: "absolute", inset: 0, background: "color-mix(in srgb, var(--app-card-background) 45%, transparent)" }} />
      )}
      {/* Header row — square avatar on the left, name + meta on the right.
          The avatar slot is fixed-size (112 × 112) so text alignment stays
          consistent across photo / no-photo / long-name cases. */}
      <div
        style={{
          position: "relative",
          display: "flex",
          alignItems: "center",
          gap: "var(--spacing-md)",
          marginBottom: compact ? 0 : "var(--spacing-md)",
        }}
      >
        {/* A shape frame is a mask, and a mask cuts away any shadow on the element it is on: the outline is drawn by a
            shadow on the box round it. Without a photo the shape takes a tint of the pet's colour, or it would be the
            card's own colour and vanish. */}
        <div style={{ flexShrink: 0, width: `${slot}px`, height: `${slot}px`, filter: shapedFrame ? "drop-shadow(0 0 1px rgba(0, 0, 0, 0.45))" : undefined }}>
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
            width: `${slot}px`,
            height: `${slot}px`,
            cursor: pet.photo_url ? "pointer" : "default",
            borderRadius: "var(--radius-md)",
            overflow: "hidden",
            background: "var(--app-accent-soft)",
            color: "var(--app-accent-deep)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            ...frame.box,
            ...(shapedFrame && !pet.photo_url ? { background: "color-mix(in srgb, var(--app-accent-deep) 18%, var(--app-card-background))" } : {}),
          }}
        >
          {pet.photo_url ? (
            <PetPhotoFill
              src={pet.photo_url}
              alt={pet.name}
              size={slot}
              priority
              crop={petCropOf(look)}
              style={frame.image}
            />
          ) : (
            // With a frame, the icon sits on the frame's own mat, which can be dark or metallic: it gets the card's
            // ground behind it, so the accent colour reads on it in both themes (the mat's colour is not the card's).
            createElement(SpeciesIcon, {
              size: slot / 2,
              strokeWidth: 1.6,
              style: Object.keys(frame.box).length
                ? { display: "block", background: "var(--app-card-background)", borderRadius: "50%", padding: slot / 12, boxSizing: "content-box" }
                : { display: "block" },
              "aria-hidden": true,
            })
          )}
        </div>
        </div>

        {/* Right column — name and the age, breed and gender line.
            minWidth: 0 lets flex children ellipsis correctly. */}
        <div
          style={{
            flex: 1,
            minWidth: 0,
            display: "flex",
            flexDirection: "column",
            gap: "var(--spacing-sm)",
            // Over a photo backdrop each letter gets a halo in the card's own colour, not a box: the photo stays whole, and the
            // name, the line and the meta read on any part of it, white or black, in both themes.
            ...(backdrop === "photo"
              ? { textShadow: "0 0 3px var(--app-card-background), 0 0 7px var(--app-card-background)" }
              : {}),
          }}
        >
          <div
            className="display-headline"
            style={{
              fontSize: compact ? "var(--text-lg)" : "var(--text-xl)",
              fontWeight: 700,
              color: "var(--app-text-primary)",
              // Two lines before a cut: a long name is still a name.
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
              overflowWrap: "anywhere",
              ...petFontStyle(font, compact ? "var(--text-lg)" : "var(--text-xl)"),
              ...(fontReady ? {} : { visibility: "hidden" }),
            }}
          >
            {pet.name}
          </div>

          {/* The line the family put under the name; the pet's own colour reaches the avatar tint and this line. */}
          {look.tagline && (
            <div
              style={{
                fontSize: "var(--text-sm)",
                fontWeight: 500,
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
          {!compact && (
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
          )}
          {!compact && canFillIn && (
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
                fontWeight: 500,
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