/**
 * Icon keys for event types. The event-type registry stores an icon by
 * this string key (not a component), so it can round-trip through the
 * API/DB; this map is the one place that resolves a key to a lucide
 * component, for both display and the "create event type" icon picker.
 */
import {
  Utensils,
  Scale,
  Wind,
  Toilet,
  Shovel,
  Eye,
  Toothbrush,
  Ear,
  Pill,
  PawPrint,
  Heart,
  Zap,
  Moon,
  Sun,
  Droplet,
  Bone,
  Syringe,
  Thermometer,
  Camera,
  Gift,
  Star,
  Smile,
  Bell,
  Calendar,
  type LucideIcon,
} from 'lucide-react';

export const ICON_REGISTRY: Record<string, LucideIcon> = {
  utensils: Utensils,
  scale: Scale,
  wind: Wind,
  toilet: Toilet,
  shovel: Shovel,
  eye: Eye,
  toothbrush: Toothbrush,
  ear: Ear,
  pill: Pill,
  paw: PawPrint,
  heart: Heart,
  zap: Zap,
  moon: Moon,
  sun: Sun,
  droplet: Droplet,
  bone: Bone,
  syringe: Syringe,
  thermometer: Thermometer,
  camera: Camera,
  gift: Gift,
  star: Star,
  smile: Smile,
  bell: Bell,
  calendar: Calendar,
};

/** Fallback for an icon key that isn't (or is no longer) in the registry. */
export const FALLBACK_ICON: LucideIcon = PawPrint;

export function getEventIcon(key: string): LucideIcon {
  return ICON_REGISTRY[key] ?? FALLBACK_ICON;
}

/** Options for an icon-picker grid, in a stable, curated order. */
export const ICON_OPTIONS: { key: string; Icon: LucideIcon }[] = Object.entries(ICON_REGISTRY).map(
  ([key, Icon]) => ({ key, Icon })
);
