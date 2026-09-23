import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { setSessionExpiredHandler } from './services/api';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Navbar } from './components/Navbar';
import { BottomTabBar } from './components/BottomTabBar';
import { ThemeProvider } from './components/ThemeProvider';
import { LoadingSpinner } from './components/LoadingSpinner';
import { ErrorBoundary } from './components/ErrorBoundary';
import { HapticListener } from './components/HapticListener';
import { RouteTransition } from './components/RouteTransition';

// Lazy load pages for code splitting. Every route is split, Dashboard
// included: these five used to be eager imports, which meant every
// route — even /login — paid for downloading and parsing History (and
// the recharts it pulls in), AdminPanel, Settings and MedicationsList
// before the app could render anything.
const Login = lazy(() => import('./pages/Login').then(m => ({ default: m.Login })));
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const History = lazy(() => import('./pages/History').then(m => ({ default: m.History })));
const HealthRecordForm = lazy(() => import('./pages/HealthRecordForm').then(m => ({ default: m.HealthRecordForm })));
const AdminPanel = lazy(() => import('./pages/AdminPanel').then(m => ({ default: m.AdminPanel })));
const UserForm = lazy(() => import('./pages/UserForm').then(m => ({ default: m.UserForm })));
const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })));
const Pets = lazy(() => import('./pages/Pets').then(m => ({ default: m.Pets })));
const UserProfile = lazy(() => import('./pages/UserProfile').then(m => ({ default: m.UserProfile })));
const PetForm = lazy(() => import('./pages/PetForm').then(m => ({ default: m.PetForm })));
const FormDefaults = lazy(() => import('./pages/FormDefaults').then(m => ({ default: m.FormDefaults })));
const TilesSettings = lazy(() => import('./pages/TilesSettings').then(m => ({ default: m.TilesSettings })));
const EventTypesSettings = lazy(() => import('./pages/EventTypesSettings').then(m => ({ default: m.EventTypesSettings })));
const EventTypeForm = lazy(() => import('./pages/EventTypeForm').then(m => ({ default: m.EventTypeForm })));
const MedicationsList = lazy(() => import('./pages/MedicationsList').then(m => ({ default: m.MedicationsList })));
const MedicationForm = lazy(() => import('./pages/MedicationForm').then(m => ({ default: m.MedicationForm })));
const DocumentsList = lazy(() => import('./pages/DocumentsList').then(m => ({ default: m.DocumentsList })));
const DocumentForm = lazy(() => import('./pages/DocumentForm').then(m => ({ default: m.DocumentForm })));

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
      navigate('/login', { replace: true });
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

function AppRoutes() {
  return (
    <>
      <SessionExpiryBridge />
      <Navbar />
      <Suspense fallback={<LoadingSpinner />}>
        <RouteTransition>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Dashboard />
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
                  <HealthRecordForm />
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
                  <MedicationForm />
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
                  <DocumentForm />
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
              path="/form-defaults"
              element={
                <ProtectedRoute>
                  <FormDefaults />
                </ProtectedRoute>
              }
            />
            <Route
              path="/tiles-settings"
              element={
                <ProtectedRoute>
                  <TilesSettings />
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
      <BottomTabBar />
    </>
  );
}

function App() {
  // Use root path everywhere - no basename needed
  const basename = '/';

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={basename}>
        <ThemeProvider>
          <HapticListener />
          <ErrorBoundary>
            <AppRoutes />
          </ErrorBoundary>
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
