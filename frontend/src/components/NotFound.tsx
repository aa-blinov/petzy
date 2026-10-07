import { useNavigate } from 'react-router-dom';
import { Compass } from 'lucide-react';
import { EmptyState } from './EmptyState';

/**
 * An address the app has no screen for.
 *
 * Before, any unknown address answered with a jump to the feed: an old link to a course, a typo,
 * a truncated address — the person found themselves on the feed with no word about it, and the
 * only sign that the address was wrong was that what they wanted was not there. Saying so is the
 * whole point of this screen.
 */
export function NotFound() {
  const navigate = useNavigate();
  return (
    <div className="page-container">
      <div className="max-width-container safe-area-padding">
        <EmptyState
          icon={Compass}
          title="Такого адреса нет"
          description="Ссылка устарела или в адресе опечатка"
          actionLabel="На ленту"
          onAction={() => navigate('/', { replace: true })}
        />
      </div>
    </div>
  );
}