/** The clinics and doctors a record's form offers to choose from. Pure: the form hands it what it has read, it hands back the
    names in the order they are offered. */

export interface ProfileClinic {
  name?: string | null;
  doctors: { name: string }[];
}

export interface PlaceSources {
  /** The clinics of this pet's medical profile, each with its doctors. */
  profileClinics: ProfileClinic[];
  /** The clinic and the doctor of the records of this pet the card shows. */
  records: { clinic?: string | null; vet?: string | null }[];
  /** Every clinic the person has named for the pets they can reach (the server's `places`). */
  knownClinics: string[];
  /** Every doctor, with the clinic he was seen at when it is known. */
  knownDoctors: { name: string; clinic: string | null }[];
  /** The clinic and the doctor chosen in the form now. */
  clinicValue?: string | null;
  vetValue?: string | null;
}

const same = (a?: string | null, b?: string | null) => !!a && !!b && a.trim().toLowerCase() === b.trim().toLowerCase();

/** The names without repeats (case and edge spaces do not make a second one), the value now chosen kept at the end if it is new. */
export function distinctNames(names: (string | null | undefined)[], current?: string | null): string[] {
  const out: string[] = [];
  for (const n of [...names, current]) {
    const name = n?.trim();
    if (name && !out.some((o) => same(o, name))) out.push(name);
  }
  return out;
}

export function clinicNames(s: PlaceSources): string[] {
  return distinctNames([...s.profileClinics.map((c) => c.name), ...s.records.map((r) => r.clinic), ...s.knownClinics], s.clinicValue);
}

/**
 * With a clinic chosen only its own doctors are offered (a one-off clinic has none of the profile's), so a doctor never changes
 * a clinic that was picked: the clinic follows the doctor only when none was chosen. A doctor named for another pet is offered
 * with the clinic he was seen at: next to that clinic, or when none is chosen.
 */
export function doctorNames(s: PlaceSources): string[] {
  const clinicChosen = !!s.clinicValue?.trim();
  const chosen = s.profileClinics.find((c) => same(c.name, s.clinicValue));
  const clinicOf = (doctor: string) => s.profileClinics.find((c) => c.doctors.some((d) => same(d.name, doctor)));
  return distinctNames(
    [
      ...(clinicChosen ? (chosen ? chosen.doctors : []) : s.profileClinics.flatMap((c) => c.doctors)).map((d) => d.name),
      ...s.records
        .map((r) => r.vet)
        .filter((v) => !clinicChosen || !chosen || !clinicOf(v ?? '') || same(clinicOf(v ?? '')?.name, chosen.name)),
      ...s.knownDoctors.filter((d) => !clinicChosen || !d.clinic || same(d.clinic, s.clinicValue)).map((d) => d.name),
    ],
    s.vetValue,
  );
}
