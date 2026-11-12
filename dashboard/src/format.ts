const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});
const day = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeZone: "UTC",
});
const moment = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
});
const clock = new Intl.DateTimeFormat("en-US", { timeStyle: "medium" });

/** An amount in US dollars, such as $1,250.00. */
export function money(amount: number): string {
  return dollars.format(amount);
}

/** A calendar date such as 2026-06-18, shown as Jun 18, 2026. */
export function date(isoDate: string): string {
  return day.format(new Date(isoDate));
}

/** A moment in time, shown in the viewer's time zone. */
export function dateTime(isoTime: string): string {
  return moment.format(new Date(isoTime));
}

/** The time of day of a moment, such as 3:04:05 PM. */
export function time(isoTime: string): string {
  return clock.format(new Date(isoTime));
}

/** A code such as trip_delay, shown as Trip delay. */
export function humanize(code: string): string {
  const words = code.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
