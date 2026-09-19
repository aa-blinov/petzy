/**
 * Skeleton placeholders for list/card loading states.
 *
 * Mimics the silhouette of HistoryItem, PetCard and MedicationCard
 * so the swap from skeleton → real card is visually seamless.
 */

export function HistoryItemSkeleton() {
  return (
    <div className="card-soft" style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: '12px',
      padding: '14px',
    }}>
      <div className="skeleton" style={{ width: 44, height: 44, borderRadius: 14, flexShrink: 0 }} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div className="skeleton" style={{ height: 14, width: '45%' }} />
        <div className="skeleton" style={{ height: 10, width: '30%' }} />
        <div className="skeleton" style={{ height: 12, width: '65%' }} />
      </div>
    </div>
  );
}

export function PetCardSkeleton() {
  return (
    <div className="card-soft" style={{ overflow: 'hidden' }}>
      <div className="skeleton" style={{ width: '100%', height: 120, borderRadius: 0 }} />
      <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div className="skeleton" style={{ height: 20, width: '40%' }} />
        <div className="skeleton" style={{ height: 12, width: '25%' }} />
      </div>
    </div>
  );
}

export function MedicationCardSkeleton() {
  return (
    <div className="card-soft" style={{ padding: '20px' }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
        <div className="skeleton" style={{ width: 36, height: 36, borderRadius: 12 }} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div className="skeleton" style={{ height: 16, width: '45%' }} />
          <div className="skeleton" style={{ height: 12, width: '60%' }} />
        </div>
      </div>
      <div className="skeleton" style={{ height: 10, width: '80%', marginBottom: 8 }} />
      <div className="skeleton" style={{ height: 10, width: '65%' }} />
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      {/* Pet hero skeleton */}
      <div className="card-soft" style={{ overflow: 'hidden' }}>
        <div className="skeleton" style={{ width: '100%', height: 180, borderRadius: 0 }} />
        <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="skeleton" style={{ height: 14, width: '30%' }} />
          <div style={{ display: 'flex', gap: 8 }}>
            <div className="skeleton" style={{ flex: 1, height: 56, borderRadius: 12 }} />
            <div className="skeleton" style={{ flex: 1, height: 56, borderRadius: 12 }} />
          </div>
        </div>
      </div>
      <div className="skeleton" style={{ height: 24, width: 80, marginTop: 4 }} />
      <HistoryItemSkeleton />
      <HistoryItemSkeleton />
      <HistoryItemSkeleton />
    </div>
  );
}
