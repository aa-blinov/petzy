import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Dialog } from 'antd-mobile';
import { accountService, ACCOUNT_QUERY_KEY } from '../services/account.service';
import { legalService, LEGAL_QUERY_KEY } from '../services/legal.service';
import { httpStatus } from '../services/api';
import { useSession } from '../hooks/useSession';
import { useAuth } from '../hooks/useAuth';
import { isPublicPage } from '../utils/publicPages';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { LoadError } from './LoadError';

/** Where the question must not block: reading the texts, or leaving instead. */
const FREE_PAGES = ['/settings/delete-account'];

/**
 * Asks for consent to the privacy policy from an account that hasn't given
 * it for the current version: made by the admin, made before the policy
 * existed, or the policy changed since (web/legal.py PRIVACY_POLICY_VERSION).
 */
export function PrivacyConsentGate() {
  const { username } = useSession();
  const { logout } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const enabled = !!username && !isPublicPage(pathname);
  const freePage = FREE_PAGES.includes(pathname);

  const { data: account, error: accountError, refetch: refetchAccount } = useQuery({
    queryKey: ACCOUNT_QUERY_KEY,
    queryFn: () => accountService.get(),
    enabled,
  });
  const needed = enabled && !!account?.privacy_consent_needed && !freePage;
  // The account did not answer, so whether consent is still owed is not known. The question stays up with a way
  // to ask again instead of vanishing. A 401 is the session ending, and the session check already handles that.
  const accountUnknown = enabled && !account && !!accountError && httpStatus(accountError) !== 401 && !freePage;
  const { data: legal, isError: legalFailed, refetch: refetchLegal } = useQuery({
    queryKey: LEGAL_QUERY_KEY,
    queryFn: () => legalService.get(),
    enabled: needed,
  });

  const accept = async () => {
    if (!legal) return;
    setBusy(true);
    try {
      await legalService.acceptPrivacyPolicy(legal.policy_version);
      await queryClient.invalidateQueries({ queryKey: ACCOUNT_QUERY_KEY });
      await queryClient.invalidateQueries({ queryKey: LEGAL_QUERY_KEY });
    } catch (err) {
      showToast.failure(getApiErrorMessage(err, 'Не удалось сохранить согласие'));
    } finally {
      setBusy(false);
    }
  };

  const link = (href: string, text: string) => (
    <a href={href} target="_blank" rel="noopener" style={{ color: 'var(--app-accent-deep)', fontWeight: 500 }}>
      {text}
    </a>
  );

  return (
    <Dialog
      visible={needed || accountUnknown}
      title="Согласие на обработку данных"
      aria-label="Согласие на обработку данных"
      content={
        accountUnknown ? (
          <LoadError what="сведения об аккаунте" onRetry={refetchAccount} compact />
        ) : (
          <>
            <div style={{ lineHeight: 1.5 }}>
              Чтобы пользоваться Petzy дальше, нужно ваше {link('/consent', 'согласие на обработку персональных данных')}
              Как мы с ними обращаемся, написано в {link('/privacy', 'политике конфиденциальности')}
            </div>
            {/* Without the text the button below cannot be pressed: this says why and offers to ask again. */}
            {legalFailed && !legal && <LoadError what="текст" onRetry={refetchLegal} compact />}
          </>
        )
      }
      closeOnMaskClick={false}
      getContainer={() => document.body}
      actions={[
        { key: 'accept', text: 'Даю согласие', bold: true, disabled: busy || !legal, onClick: accept },
        { key: 'delete', text: 'Удалить аккаунт', onClick: () => navigate('/settings/delete-account') },
        { key: 'logout', text: 'Выйти', onClick: () => logout() },
      ]}
    />
  );
}
