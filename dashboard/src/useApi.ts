import { useCallback, useEffect, useState } from "react";
import { getJson, type ApiPath } from "./api";

export const POLL_MS = 2000;

interface Loaded<T> {
  path: string;
  data?: T;
  error?: string;
}

interface ApiResult<T> {
  data: T | undefined;
  error: string | undefined;
  reload: () => void;
}

/** Load a path from the API, and by default load it again every two seconds. */
export function useApi<T>(path: ApiPath<T> | null, poll = true): ApiResult<T> {
  const [loaded, setLoaded] = useState<Loaded<T>>();
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (path === null) return;
    let active = true;
    const load = () => {
      getJson(path).then(
        (data) => {
          if (active) setLoaded({ path, data });
        },
        (error: unknown) => {
          if (active)
            setLoaded((last) => ({
              path,
              data: last?.path === path ? last.data : undefined,
              error: error instanceof Error ? error.message : String(error),
            }));
        },
      );
    };
    load();
    const timer = poll ? setInterval(load, POLL_MS) : undefined;
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [path, poll, version]);

  const reload = useCallback(() => {
    setVersion((last) => last + 1);
  }, []);
  const current = path !== null && loaded?.path === path ? loaded : undefined;
  return { data: current?.data, error: current?.error, reload };
}
