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

/** What each icon is called in Russian: what a screen reader says when the icon picker offers it, and what a person
 *  would look for («Глаза», «Уши»). The key stays the one the registry stores. */
export const ICON_LABELS: Record<string, string> = {
  utensils: 'Кормление',
  scale: 'Вес',
  wind: 'Дыхание',
  toilet: 'Туалет',
  shovel: 'Наполнитель',
  eye: 'Глаза',
  toothbrush: 'Зубы',
  ear: 'Уши',
  pill: 'Таблетка',
  paw: 'Лапа',
  heart: 'Сердце',
  zap: 'Энергия',
  moon: 'Ночь',
  sun: 'День',
  droplet: 'Капли',
  bone: 'Кость',
  syringe: 'Укол',
  thermometer: 'Термометр',
  camera: 'Камера',
  gift: 'Подарок',
  star: 'Звезда',
  smile: 'Улыбка',
  bell: 'Напоминание',
  calendar: 'Календарь',
};

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
export const ICON_OPTIONS: { key: string; Icon: LucideIcon; label: string }[] = Object.entries(ICON_REGISTRY).map(
  ([key, Icon]) => ({ key, Icon, label: ICON_LABELS[key] ?? key })
);
