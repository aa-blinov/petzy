/** Per-user "I'm waiting for someone to share a pet with me" flag — lets a
 *  co-owner with zero pets of their own use the app without being sent back
 *  into onboarding on every visit to the dashboard. */
const key = (username: string | null) => `petzy:onboardingDismissed:${username ?? ''}`;

export function isOnboardingDismissed(username: string | null): boolean {
  try {
    return localStorage.getItem(key(username)) === '1';
  } catch {
    return false;
  }
}

export function dismissOnboarding(username: string | null): void {
  try {
    localStorage.setItem(key(username), '1');
  } catch {
    // Private mode / blocked storage: the worst case is seeing onboarding again.
  }
}
