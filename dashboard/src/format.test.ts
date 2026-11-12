import { expect, it } from "vitest";
import { date, dateTime, humanize, money, time } from "./format";

it("shows money in US dollars", () => {
  expect(money(1250)).toBe("$1,250.00");
  expect(money(0)).toBe("$0.00");
  expect(money(99.5)).toBe("$99.50");
});

it("shows calendar dates as they are, whatever the time zone", () => {
  expect(date("2026-06-18")).toBe("Jun 18, 2026");
  expect(date("2026-01-01")).toBe("Jan 1, 2026");
});

it("shows moments in time", () => {
  expect(dateTime("2026-11-09T22:33:00+00:00")).toMatch(/Nov (9|10), 2026/);
  expect(time("2026-11-09T22:33:05+00:00")).toMatch(/\d{1,2}:\d{2}:05/);
});

it("turns codes into words", () => {
  expect(humanize("trip_delay")).toBe("Trip delay");
  expect(humanize("premium")).toBe("Premium");
});
