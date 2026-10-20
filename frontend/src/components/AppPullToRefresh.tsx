import type { ReactNode } from 'react';
import { PullToRefresh } from 'antd-mobile';

import { hapticFeedback } from '../utils/haptic';

/**
 * «Потянуть для обновления» на экранах-вкладках: один жест, один отклик, одно место.
 *
 * На ленте жест был, на медкарте и в настройках его не было вовсе, а в лекарствах и документах
 * он пропадал вместе с пустым списком: человек тянул вниз, и ничего не происходило, хотя свежие
 * данные нужны именно там. Пустой экран тоже обновляется: это и есть экран, который открывают,
 * чтобы что-то записать с телефона, а запись могли сделать с другого.
 */
export function AppPullToRefresh({
    onRefresh,
    children,
}: {
    onRefresh: () => Promise<unknown> | unknown;
    children: ReactNode;
}) {
    return (
        <PullToRefresh
            headHeight={48}
            onRefresh={async () => {
                hapticFeedback('medium');
                await onRefresh();
            }}
        >
            {children}
        </PullToRefresh>
    );
}
