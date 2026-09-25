import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { PawPrint, UserRound } from 'lucide-react';
import { usersService } from '../services/users.service';
import { UserAvatar } from '../components/UserAvatar';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { EmptyState } from '../components/EmptyState';

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

  const { data: profile, isLoading, error } = useQuery({
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
    return (
      <div className="page-container">
        <div className="max-width-container">
          <EmptyState
            icon={UserRound}
            title="Профиль недоступен"
            description={
              status === 404
                ? 'Такого пользователя нет, или у вас нет общего питомца с ним'
                : 'Не удалось загрузить профиль. Попробуйте ещё раз'
            }
          />
        </div>
      </div>
    );
  }

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
          <h2 className="section-header" style={{ marginBottom: 10, paddingLeft: 4 }}>
            Общие питомцы
          </h2>
          {profile.shared_pets.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {profile.shared_pets.map((petName) => (
                <div
                  key={petName}
                  className="card-soft"
                  style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: '10px' }}
                >
                  <PawPrint size={18} strokeWidth={2} style={{ color: 'var(--app-accent-deep)' }} />
                  <span style={{ fontWeight: 500 }}>{petName}</span>
                </div>
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
