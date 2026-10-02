import { useNavigate } from 'react-router-dom';
import { PawPrint } from 'lucide-react';
import { EmptyState } from './EmptyState';

/** A screen that is about one pet, opened by someone who has none yet: what to do, not a blank page. */
export function NoPetState({ what }: { what: string }) {
  const navigate = useNavigate();
  return (
    <div className="page-container">
      <div className="max-width-container">
        <EmptyState
          icon={PawPrint}
          title="Сначала добавьте питомца"
          description={`Когда в Petzy будет питомец, здесь появится раздел «${what}»`}
          actionLabel="Добавить питомца"
          onAction={() => navigate('/pets/new')}
        />
      </div>
    </div>
  );
}
