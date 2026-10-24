import { useCallback, useState } from 'react';

/**
 * What the date fields of a form say about the dates typed into them. A typed date that is unfinished or impossible never
 * reaches the form's value, so the form would otherwise save the older date without a word: `blocked()` tells it to refuse,
 * and `refuse()` makes the fields show what is wrong.
 */
export function useTypedDateProblems() {
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [refusals, setRefusals] = useState(0);

  const report = useCallback(
    (name: string) => (message: string) =>
      setProblems((current) => {
        if ((current[name] ?? '') === message) return current;
        const next = { ...current };
        if (message) next[name] = message;
        else delete next[name];
        return next;
      }),
    [],
  );
  const blocked = Object.keys(problems).length > 0;
  /** True when the save has to stop; the fields then show their messages. */
  const refuse = () => {
    if (blocked) setRefusals((n) => n + 1);
    return blocked;
  };
  return { report, blocked, refuse, refusals };
}
