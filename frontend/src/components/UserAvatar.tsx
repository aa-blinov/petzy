import { pastelColorMap, TILE_COLORS } from '../utils/constants';

/** Fixed palette (the same pastel tile colors used everywhere else in the
 *  app) rather than one derived per-avatar — keeps a person's color
 *  consistent across renders without needing to store one. */
const AVATAR_COLORS = Object.keys(TILE_COLORS);

/** Deterministic pick from AVATAR_COLORS — the same username always lands
 *  on the same color, so a person's avatar doesn't change between renders
 *  or across devices. */
function colorForUsername(username: string): string {
  let hash = 0;
  for (let i = 0; i < username.length; i++) {
    hash = (hash * 31 + username.charCodeAt(i)) >>> 0;
  }
  return AVATAR_COLORS[hash % AVATAR_COLORS.length];
}

/** "Мария Петрова" -> "МП", "admin" -> "A". Falls back to the username
 *  when there's no full name — most accounts won't have one filled in. */
function initialsFor(username: string, fullName?: string | null): string {
  const name = fullName?.trim();
  if (name) {
    const parts = name.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return parts[0][0].toUpperCase();
  }
  return username.slice(0, 1).toUpperCase();
}

interface UserAvatarProps {
  username: string;
  fullName?: string | null;
  /** Diameter in pixels. */
  size?: number;
  style?: React.CSSProperties;
}

/** A circular initials avatar for a user — pets get a photo or a species
 *  icon on a rounded-square tile (see PetImage); users have no photo
 *  field, and a circle keeps the two shapes from being confused at a
 *  glance in the same list (e.g. a document card showing both). */
export function UserAvatar({ username, fullName, size = 28, style }: UserAvatarProps) {
  const color = pastelColorMap[colorForUsername(username)];
  return (
    <div
      aria-hidden
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        backgroundColor: color,
        color: 'var(--app-text-on-tile)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: Math.max(10, Math.round(size * 0.4)),
        fontWeight: 700,
        flexShrink: 0,
        lineHeight: 1,
        ...style,
      }}
    >
      {initialsFor(username, fullName)}
    </div>
  );
}
