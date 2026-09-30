/** The IANA name of this device's time zone (Asia/Almaty), or undefined when
    the browser won't say. The server stores the clock a time was entered on
    and uses this name to show it on someone else's clock in an export. */
export function deviceTimeZone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
  }
}
