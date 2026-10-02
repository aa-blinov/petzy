import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { usePet } from '../hooks/usePet';
import { NoPetState } from './NoPetState';

/** A screen that writes something about a pet: without a pet it says to add one, instead of a form that would be
 *  filled in and then refused. While the list is not known yet it waits (the screen itself shows its own loading). */
export function RequirePet({ what, children }: { what: string; children: ReactNode }) {
  const { pets, isFetched, isError } = usePet();
  if (isFetched && !isError && pets.length === 0) return <NoPetState what={what} />;
  return <>{children}</>;
}

/** The «Медкарта» tab with no pet to open: the same words, on that tab. */
export function MedicalCardEntry() {
  const { pets, selectedPetId, isFetched } = usePet();
  // A pet is known (chosen, or the first of the list): that is the card to open.
  const target = selectedPetId ?? pets[0]?._id;
  if (target) return <Navigate to={`/pets/${target}/medical-card`} replace />;
  if (!isFetched) return null;
  return <NoPetState what="Медкарта" />;
}
