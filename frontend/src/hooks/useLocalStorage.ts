import { useState, useEffect, useCallback } from 'react';

export function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T) => void] {
  // State to store our value
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.error(`Error loading localStorage key "${key}":`, error);
      return initialValue;
    }
  });

  // Return a wrapped version of useState's setter function that
  // persists the new value to localStorage.
  const setValue = useCallback((value: T) => {
    try {
      setStoredValue(value);
      window.localStorage.setItem(key, JSON.stringify(value));
      // Dispatch custom event for same-tab synchronization
      window.dispatchEvent(new CustomEvent('local-storage-change', {
        detail: { key, value }
      }));
    } catch (error) {
      console.error(`Error setting localStorage key "${key}":`, error);
    }
  }, [key]);

  // Listen for changes from other components (same tab)
  useEffect(() => {
    const handleStorageChange = (e: CustomEvent<{ key: string; value: T }>) => {
      if (e.detail.key === key) {
        setStoredValue(e.detail.value);
      }
    };

    // Listen for changes from other tabs
    const handleWindowStorage = (e: StorageEvent) => {
      if (e.key === key && e.newValue !== null) {
        try {
          setStoredValue(JSON.parse(e.newValue));
        } catch {
          // Ignore parse errors
        }
      }
    };

    window.addEventListener('local-storage-change', handleStorageChange as EventListener);
    window.addEventListener('storage', handleWindowStorage);

    return () => {
      window.removeEventListener('local-storage-change', handleStorageChange as EventListener);
      window.removeEventListener('storage', handleWindowStorage);
    };
  }, [key]);

  return [storedValue, setValue];
}
