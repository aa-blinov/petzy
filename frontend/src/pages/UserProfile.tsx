import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { PawPrint, UserRound } from 'lucide-react';
import { usersService, type UserPublicProfile } from '../services/users.service';
import { UserAvatar } from '../components/UserAvatar';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { EmptyState } from '../components/EmptyState';

/** A pet both people can see, as the profile gives it: the id opens its medical card. */
type SharedPet = { id: string; name: string };

/** shared_pets as id and name. A pet given by name alone (an answer from a server
 *  that has not been updated yet, or one the service worker kept) has no id, and
 *  a name with no card to open is not a link: it is left out of the list.
 *  NOTE: users.service.ts still types shared_pets as string[]; the type there
 *  wants this too (shared_pets: SharedPetRef[]), which is why this reads it as
 *  unknown and checks rather than believing the type. */
function sharedPetsOf(profile: UserPublicProfile): SharedPet[] {
  const raw: unknown = profile.shared_pets;
  if (!Array.isArray(raw)) return [];
  const pets: SharedPet[] = [];
  for (const item of raw) {
    if (typeof item !== 'object' || item === null) continue;
    const { id, name } = item as Partial<SharedPet>;
    if (typeof id === 'string' && id && typeof name === 'string' && name) pets.push({ id, name });
  }
  return pets;
}

/** "2024-01-15 14:30" -> "с января 2024". Only the API's own
 *  "YYYY-MM-DD HH:MM" shape is ever handed to this, so the split is safe
 *  without pulling in the fuller relativeTime date parser. */
function memberSince(createdAt: string): string {
  const [datePart] = createdAt.split(' ');
  const [year, month] = datePart.split('-').map(Number);
  if (!year || !month) return '';
  const months = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
  ];
  return `с ${months[month - 1]} ${year}`;
}

export function UserProfile() {
  const { username } = useParams<{ username: string }>();
  const navigate = useNavigate();

  const { data: profile, isLoading, error, refetch } = useQuery({
    queryKey: ['user-profile', username],
    queryFn: () => usersService.getPublicProfile(username!),
    enabled: !!username,
    retry: false,
  });

  if (isLoading) {
    return <LoadingSpinner />;
  }

  if (error || !profile) {
    // A 404 here means either the username doesn't exist or the viewer
    // doesn't share a pet with them — the backend deliberately doesn't
    // distinguish the two (see web/users.py), so neither does this.
    const status = isAxiosError(error) ? error.response?.status : undefined;
    const notFound = status === 404;
    return (
      // role="alert": the state arrived without anything saying it. A screen reader on this page read nothing
      // at all and the person had no idea the profile hadn't loaded.
      <div className="page-container" role="alert">
        <div className="max-width-container">
          <EmptyState
            icon={UserRound}
            heading="h1"
            title="Профиль недоступен"
            description={
              notFound
                ? 'Такого пользователя нет, или у вас нет общего питомца с ним'
                : 'Не удалось загрузить профиль. Сервер не ответил'
            }
            // A failed request had a «попробуйте ещё раз» with nothing to press.
            {...(notFound ? {} : { actionLabel: 'Повторить', onAction: () => { void refetch(); } })}
          />
        </div>
      </div>
    );
  }

  const sharedPets = sharedPetsOf(profile);

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div
          className="safe-area-padding"
          style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--spacing-md)', paddingTop: 'var(--spacing-lg)' }}
        >
          <UserAvatar username={profile.username} fullName={profile.full_name} size={88} />
          <div style={{ textAlign: 'center' }}>
            <h1 className="display-headline" style={{ fontSize: 'var(--text-xl)', fontWeight: 700, margin: 0 }}>
              {profile.full_name || profile.username}
            </h1>
            {profile.full_name && (
              <div style={{ color: 'var(--app-text-secondary)', fontSize: 'var(--text-sm)' }}>
                @{profile.username}
              </div>
            )}
            {profile.created_at && (
              <div style={{ color: 'var(--app-text-tertiary)', fontSize: 'var(--text-sm)', marginTop: 4 }}>
                На Petzy {memberSince(profile.created_at)}
              </div>
            )}
          </div>
        </div>

        <div className="safe-area-padding" style={{ marginTop: 'var(--spacing-xl)' }}>
          <h2 className="section-header" style={{ marginBottom: 'var(--spacing-sm)', paddingLeft: 4 }}>
            Общие питомцы
          </h2>
          {sharedPets.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
              {sharedPets.map((pet) => (
                <button
                  key={pet.id}
                  type="button"
                  className="card-soft card-soft--interactive"
                  onClick={() => navigate(`/pets/${pet.id}/medical-card`)}
                  style={{
                    padding: 'var(--spacing-lg)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--spacing-md)',
                    width: '100%',
                    textAlign: 'left',
                    font: 'inherit',
                    color: 'inherit',
                    cursor: 'pointer',
                    minHeight: 'var(--touch-min)',
                  }}
                >
                  <PawPrint size={18} strokeWidth={2} style={{ color: 'var(--app-accent-deep)' }} />
                  <span style={{ fontWeight: 500, flex: 1 }}>{pet.name}</span>
                  {/* The medical card checks access on the server (require_pet_access),
                      so opening it here grants nothing a shared user did not already have. */}
                  <span aria-hidden style={{ color: 'var(--app-text-tertiary)' }}>›</span>
                </button>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--app-text-secondary)', fontSize: 'var(--text-sm)' }}>
              Нет общих питомцев
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
