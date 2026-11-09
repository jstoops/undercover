import { render } from "@testing-library/react";
import { createElement } from "react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";
import { AppRoutes } from "./App";

/**
 * Answer fetch from a table of "METHOD /path" to JSON; anything else is a 404.
 * onRequest runs first, so a test can change the table as requests arrive.
 */
export function stubApi(
  routes: Record<string, unknown>,
  onRequest: (key: string) => void = () => undefined,
) {
  const fetchMock = vi.fn((path: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${path}`;
    onRequest(key);
    return Promise.resolve(
      key in routes
        ? Response.json(routes[key])
        : Response.json({ detail: `No route for ${key}` }, { status: 404 }),
    );
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** Render the dashboard at a path. */
export function renderAt(path: string) {
  return render(
    createElement(
      MemoryRouter,
      { initialEntries: [path] },
      createElement(AppRoutes),
    ),
  );
}
