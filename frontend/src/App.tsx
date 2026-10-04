import { lazy, Suspense, useEffect } from 'react';
import { createBrowserRouter, RouterProvider, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { reloadIfUpdated } from './utils/swUpdate';
import { setSentryUser } from './utils/observability';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { setSessionExpiredHandler } from './services/api';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Navbar } from './components/Navbar';
import { BottomTabBar } from './components/BottomTabBar';
import { PrivacyConsentGate } from './components/PrivacyConsentGate';
import { ScrollManager } from './components/ScrollManager';
import { PetLookTheme } from './components/PetLookTheme';
import { ThemeProvider } from './components/ThemeProvider';
import { LoadingSpinner } from './components/LoadingSpinner';
import { ErrorBoundary } from './components/ErrorBoundary';
import { HapticListener } from './components/HapticListener';
import { RouteTransition } from './components/RouteTransition';
import { RouteFocus } from './components/RouteFocus';
import { Snackbar } from './components/Snackbar';
import { usePet } from './hooks/usePet';
import { useSession } from './hooks/useSession';
import { flushPendingIntakes, usePendingIntakes } from './utils/offlineIntakes';
import { documentsListQuery } from './services/documents.service';
import { medicationsListQuery } from './services/medications.service';
import { returnState } from './utils/returnTo';
import { MedicalCardEntry, RequirePet } from './components/RequirePet';

// Lazy load pages for code splitting. Every route is split, Dashboard
// included: these five used to be eager imports, which meant every
// route — even /login — paid for downloading and parsing History (and
// the recharts it pulls in), AdminPanel, Settings and MedicationsList
// before the app could render anything.
const Login = lazy(() => import('./pages/Login').then(m => ({ default: m.Login })));
const Register = lazy(() => import('./pages/Register').then(m => ({ default: m.Register })));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword').then(m => ({ default: m.ForgotPassword })));
const ResetPassword = lazy(() => import('./pages/ResetPassword').then(m => ({ default: m.ResetPassword })));
const VerifyEmail = lazy(() => import('./pages/VerifyEmail').then(m => ({ default: m.VerifyEmail })));
const AccountEmail = lazy(() => import('./pages/AccountEmail').then(m => ({ default: m.AccountEmail })));
const AccountPassword = lazy(() => import('./pages/AccountPassword').then(m => ({ default: m.AccountPassword })));
const PrivacyPolicy = lazy(() => import('./pages/Privacy').then(m => ({ default: m.PrivacyPolicy })));
const PrivacyConsent = lazy(() => import('./pages/Privacy').then(m => ({ default: m.PrivacyConsent })));
const AccountDelete = lazy(() => import('./pages/AccountDelete').then(m => ({ default: m.AccountDelete })));
const loadDashboard = () => import('./pages/Dashboard');
// The feed is where nearly every visit lands: its code is asked for while this file is evaluated, in step with the app's
// own startup, and not only once the router has rendered the route (about 0.6 s later on a slow line, then its small
// dependencies one after another).
if (typeof window !== 'undefined' && window.location.pathname === '/') void loadDashboard();
const Dashboard = lazy(() => loadDashboard().then(m => ({ default: m.Dashboard })));
const Onboarding = lazy(() => import('./pages/Onboarding').then(m => ({ default: m.Onboarding })));
const loadHistory = () => import('./pages/History');
const History = lazy(() => loadHistory().then(m => ({ default: m.History })));
const loadHealthRecordForm = () => import('./pages/HealthRecordForm');
const HealthRecordForm = lazy(() => loadHealthRecordForm().then(m => ({ default: m.HealthRecordForm })));
const AdminPanel = lazy(() => import('./pages/AdminPanel').then(m => ({ default: m.AdminPanel })));
const UserForm = lazy(() => import('./pages/UserForm').then(m => ({ default: m.UserForm })));
const loadSettings = () => import('./pages/Settings');
const Settings = lazy(() => loadSettings().then(m => ({ default: m.Settings })));
const Pets = lazy(() => import('./pages/Pets').then(m => ({ default: m.Pets })));
const UserProfile = lazy(() => import('./pages/UserProfile').then(m => ({ default: m.UserProfile })));
const PetForm = lazy(() => import('./pages/PetForm').then(m => ({ default: m.PetForm })));
const PetLookSettings = lazy(() => import('./pages/PetLookSettings').then(m => ({ default: m.PetLookSettings })));
const FormDefaults = lazy(() => import('./pages/FormDefaults').then(m => ({ default: m.FormDefaults })));
const PetEvents = lazy(() => import('./pages/PetEvents').then(m => ({ default: m.PetEvents })));
const EventTypesSettings = lazy(() => import('./pages/EventTypesSettings').then(m => ({ default: m.EventTypesSettings })));
const MedicalCard = lazy(() => import('./pages/MedicalCard').then(m => ({ default: m.MedicalCard })));
const MedicalCardSection = lazy(() => import('./pages/MedicalCardSection').then(m => ({ default: m.MedicalCardSection })));
const MedicalProfileForm = lazy(() => import('./pages/MedicalProfileForm').then(m => ({ default: m.MedicalProfileForm })));
const VisitPrepForm = lazy(() => import('./pages/VisitPrepForm').then(m => ({ default: m.VisitPrepForm })));
const MedicalRecordForm = lazy(() => import('./pages/MedicalRecordForm').then(m => ({ default: m.MedicalRecordForm })));
const EventTypeForm = lazy(() => import('./pages/EventTypeForm').then(m => ({ default: m.EventTypeForm })));
const loadMedicationsList = () => import('./pages/MedicationsList');
const MedicationsList = lazy(() => loadMedicationsList().then(m => ({ default: m.MedicationsList })));
const MedicationForm = lazy(() => import('./pages/MedicationForm').then(m => ({ default: m.MedicationForm })));
const loadDocumentsList = () => import('./pages/DocumentsList');
const DocumentsList = lazy(() => loadDocumentsList().then(m => ({ default: m.DocumentsList })));
const DocumentForm = lazy(() => import('./pages/DocumentForm').then(m => ({ default: m.DocumentForm })));
const Help = lazy(() => import('./pages/Help').then(m => ({ default: m.Help })));

/** The bottom tabs' pages and the record form (opened from the feed and
 *  history), fetched ahead of the first tap (see PrefetchTabs). */
const TAB_PAGE_LOADERS = [
  loadDashboard, loadMedicationsList, loadDocumentsList, loadHistory, loadSettings, loadHealthRecordForm,
];

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // Don't retry on 401 (unauthorized)
        if (isAxiosError(error) && error.response?.status === 401) {
          return false;
        }
        return failureCount < 1; // Retry once for other errors
      },
      // Enable request deduplication - same queries will be deduplicated automatically
      staleTime: 30 * 1000, // Consider data fresh for 30 seconds to prevent duplicate requests
      gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
    },
    mutations: {
      // The default («online») holds a save while the phone has no connection and sends it when the connection comes
      // back: the button spins, the person assumes it failed and enters the same thing again, and both arrive. Sent
      // at once instead: with no connection it fails at once, and says so (getApiErrorMessage).
      networkMode: 'always',
    },
  },
});

/**
 * Wires the axios interceptor's sign-out signal to a React Router
 * navigation, giving the app exactly one way to leave a protected page
 * when the session dies.
 *
 * Before this, api.ts did its own window.location.replace('/login')
 * while ProtectedRoute independently rendered <Navigate to="/login">.
 * Two redirects for one 401: sometimes the soft one won and the hard
 * one was skipped, sometimes both landed and the SPA rebooted on top
 * of the transition. That timing-dependent double redirect was the
 * flicker.
 */
function SessionExpiryBridge() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  useEffect(() => {
    setSessionExpiredHandler(() => {
      // Stop in-flight requests first so a late response can't
      // repopulate the cache we're about to drop.
      queryClient.cancelQueries();
      navigate('/login', { replace: true, state: returnState(window.location.pathname + window.location.search) });
      // Clear on the next macrotask, once the navigation has rendered
      // and the protected pages have unmounted. Clearing while their
      // queries still have active observers makes every one of them
      // refetch — a 401 storm on the way out. This timeout only defers
      // cache cleanup; it does not race the navigation above.
      setTimeout(() => queryClient.clear(), 0);
    });
    return () => setSessionExpiredHandler(null);
  }, [navigate, queryClient]);

  return null;
}

/**
 * Once the app is idle after start, fetch the bottom tabs' code and the
 * selected pet's documents and medications, so the first tap on a tab
 * shows its screen straight away. Without this the first visit waited on
 * the page's chunk (the old screen and tab stayed put), then flashed a
 * blank page and a one-frame skeleton before the cards; later visits,
 * with everything cached, just faded in.
 */
/** Doses marked with no connection are sent by themselves: at start, when the connection returns, when the app comes
 *  back to the front, and every half minute while any wait. */
function SendPendingIntakes() {
  const queryClient = useQueryClient();
  const pending = usePendingIntakes();
  const { isAuthenticated } = useSession();
  const waiting = pending.length > 0 && isAuthenticated !== false;

  useEffect(() => {
    if (!waiting) return;
    const send = () => void flushPendingIntakes(queryClient);
    send();
    const onVisible = () => document.visibilityState === 'visible' && send();
    window.addEventListener('online', send);
    document.addEventListener('visibilitychange', onVisible);
    const timer = setInterval(send, 30_000);
    return () => {
      window.removeEventListener('online', send);
      document.removeEventListener('visibilitychange', onVisible);
      clearInterval(timer);
    };
  }, [waiting, queryClient]);

  return null;
}

function PrefetchTabs() {
  const { selectedPetId } = usePet();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!selectedPetId) return;
    const run = () => {
      TAB_PAGE_LOADERS.forEach((load) => load().catch(() => undefined));
      queryClient.prefetchQuery(documentsListQuery(selectedPetId));
      queryClient.prefetchQuery(medicationsListQuery(selectedPetId));
    };
    // After the current screen has settled, not competing with it: on a slow connection the tabs' code and lists
    // were fetched in the same seconds as the screen's own, and held its photo and records back by about two seconds.
    // So it waits until the page has loaded and nothing is being fetched, and then for an idle moment.
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let idle: number | undefined;
    const startedAt = Date.now();
    const settled = () => {
      if (stopped) return;
      const quiet = document.readyState === 'complete' && queryClient.isFetching() === 0;
      // Never held back for good: after twelve seconds it goes anyway.
      if (!quiet && Date.now() - startedAt < 12_000) {
        timer = setTimeout(settled, 400);
        return;
      }
      if ('requestIdleCallback' in window) idle = window.requestIdleCallback(run, { timeout: 3000 });
      else timer = setTimeout(run, 500);
    };
    timer = setTimeout(settled, 400);
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      if (idle !== undefined) window.cancelIdleCallback(idle);
    };
  }, [selectedPetId, queryClient]);

  return null;
}

/** Errors in Sentry carry the signed-in login (none after signing out). */
function SentryUser() {
  const { username } = useSession();
  useEffect(() => {
    setSentryUser(username);
  }, [username]);
  return null;
}

/** A release that arrived while the app was open loads on the next main tab. */
function UpdateOnMainTabs() {
  const { pathname } = useLocation();
  useEffect(() => {
    reloadIfUpdated(pathname);
  }, [pathname]);
  return null;
}

function AppRoutes() {
  return (
    <>
      <SessionExpiryBridge />
      <PrefetchTabs />
      <SendPendingIntakes />
      <UpdateOnMainTabs />
      <SentryUser />
      <PrivacyConsentGate />
      <Snackbar />
      <PetLookTheme />
      <Navbar />
      <RouteFocus />
      <ScrollManager />
      <main id="main-content">
        <Suspense fallback={<LoadingSpinner />}>
          <RouteTransition>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/privacy" element={<PrivacyPolicy />} />
              <Route path="/consent" element={<PrivacyConsent />} />
              <Route path="/register" element={<Register />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />
              <Route path="/reset-password" element={<ResetPassword />} />
              <Route path="/verify-email" element={<VerifyEmail />} />
              <Route
                path="/welcome"
                element={
                  <ProtectedRoute>
                    <Onboarding />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <Dashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/medical-card"
                element={
                  <ProtectedRoute>
                    <MedicalCardEntry />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/history"
                element={
                  <ProtectedRoute>
                    <History />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/pets"
                element={
                  <ProtectedRoute>
                    <Pets />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/pets/new"
                element={
                  <ProtectedRoute>
                    <PetForm />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/pets/:id/edit"
                element={
                  <ProtectedRoute>
                    <PetForm />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/pets/:id/medical-card"
                element={
                  <ProtectedRoute>
                    <MedicalCard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/pets/:id/medical-card/:section"
                element={
                  <ProtectedRoute>
                    <MedicalCardSection />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/pets/:id/medical-profile"
                element={
                  <ProtectedRoute>
                    <MedicalProfileForm />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/pets/:id/visit-prep"
                element={
                  <ProtectedRoute>
                    <VisitPrepForm />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/pets/:id/medical-records/new"
                element={
                  <ProtectedRoute>
                    <MedicalRecordForm />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/pets/:id/medical-records/:recordId"
                element={
                  <ProtectedRoute>
                    <MedicalRecordForm />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/users/:username"
                element={
                  <ProtectedRoute>
                    <UserProfile />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/form/:type"
                element={
                  <ProtectedRoute>
                    <RequirePet what="Записи">
                      <HealthRecordForm />
                    </RequirePet>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/form/:type/:id"
                element={
                  <ProtectedRoute>
                    <HealthRecordForm />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin"
                element={
                  <ProtectedRoute>
                    <AdminPanel />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/users/new"
                element={
                  <ProtectedRoute>
                    <UserForm />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/admin/users/:username/edit"
                element={
                  <ProtectedRoute>
                    <UserForm />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/medications"
                element={
                  <ProtectedRoute>
                    <MedicationsList />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/medications/new"
                element={
                  <ProtectedRoute>
                    <RequirePet what="Лекарства">
                      <MedicationForm />
                    </RequirePet>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/medications/:id/edit"
                element={
                  <ProtectedRoute>
                    <MedicationForm />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/documents"
                element={
                  <ProtectedRoute>
                    <DocumentsList />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/documents/new"
                element={
                  <ProtectedRoute>
                    <RequirePet what="Документы">
                      <DocumentForm />
                    </RequirePet>
                  </ProtectedRoute>
                }
              />
              <Route
                path="/documents/:id/edit"
                element={
                  <ProtectedRoute>
                    <DocumentForm />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings"
                element={
                  <ProtectedRoute>
                    <Settings />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings/email"
                element={
                  <ProtectedRoute>
                    <AccountEmail />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings/password"
                element={
                  <ProtectedRoute>
                    <AccountPassword />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/settings/delete-account"
                element={
                  <ProtectedRoute>
                    <AccountDelete />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/pet-look"
                element={
                  <ProtectedRoute>
                    <PetLookSettings />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/form-defaults"
                element={
                  <ProtectedRoute>
                    <FormDefaults />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/pet-events"
                element={
                  <ProtectedRoute>
                    <PetEvents />
                  </ProtectedRoute>
                }
              />
              {/* The old address of the screen (a link, a bookmark, an installed app that has not updated yet). */}
              <Route path="/tiles-settings" element={<Navigate to="/pet-events" replace />} />
              <Route
                path="/help"
                element={
                  <ProtectedRoute>
                    <Help />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/event-types"
                element={
                  <ProtectedRoute>
                    <EventTypesSettings />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/event-types/new"
                element={
                  <ProtectedRoute>
                    <EventTypeForm />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/event-types/:key/edit"
                element={
                  <ProtectedRoute>
                    <EventTypeForm />
                  </ProtectedRoute>
                }
              />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </RouteTransition>
        </Suspense>
      </main>
      <BottomTabBar />
    </>
  );
}

function Shell() {
  return (
    <ThemeProvider>
      <HapticListener />
      <ErrorBoundary>
        <AppRoutes />
      </ErrorBoundary>
    </ThemeProvider>
  );
}

// A data router, not <BrowserRouter>: only it can hold a navigation back
// (useBlocker, see hooks/useUnsavedChangesGuard). One catch-all route hands
// every path to the <Routes> inside AppRoutes, so the route table itself
// stays where it was. Root path everywhere: no basename needed.
const router = createBrowserRouter([{ path: '*', element: <Shell /> }]);

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}

export default App;
