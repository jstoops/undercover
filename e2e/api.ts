import {
  expect,
  type APIRequestContext,
  type APIResponse,
} from "@playwright/test";

// The backend's API, driven the way the agent drives it: every path the
// end-to-end tests call is here. The tests never run a model.

async function ok(response: Promise<APIResponse>) {
  expect((await response).ok()).toBe(true);
}

export async function startClaim(request: APIRequestContext, claimId: string) {
  await ok(request.post(`/api/claims/${claimId}/start`));
}

export async function decide(
  request: APIRequestContext,
  claimId: string,
  decision: string,
  payout: number,
) {
  await ok(
    request.post(`/api/claims/${claimId}/decision`, {
      data: {
        decision,
        payout,
        reason:
          "The wording covers the claim. The receipts support the amount.",
        policy_section: "Section 5, Baggage and Personal Effects",
      },
    }),
  );
}

export function pay(
  request: APIRequestContext,
  claimId: string,
  amount: number,
) {
  return request.post(`/api/claims/${claimId}/payment`, { data: { amount } });
}

export async function addStep(
  request: APIRequestContext,
  claimId: string,
  step: { kind: string; name: string; content: string },
) {
  await ok(
    request.post(`/api/claims/${claimId}/steps`, {
      data: { thread_id: "e2e", ...step },
    }),
  );
}

export async function failClaim(
  request: APIRequestContext,
  claimId: string,
  reason: string,
) {
  await ok(
    request.post(`/api/claims/${claimId}/failure`, {
      data: { thread_id: "e2e", reason },
    }),
  );
}

export async function readSection(
  request: APIRequestContext,
  document: string,
  number: number,
) {
  const section = await request.get(
    `/api/documents/${document}/sections/${String(number)}`,
  );
  return section.text();
}

export async function startRun(request: APIRequestContext, cap: number) {
  const started = await request.post("/api/runs", { data: { cap } });
  return ((await started.json()) as { run_id: number }).run_id;
}

export async function saveTodos(
  request: APIRequestContext,
  runId: number,
  todos: { content: string; status: string }[],
) {
  await ok(
    request.put(`/api/runs/${String(runId)}/todos`, { data: { todos } }),
  );
}

export async function finishRun(
  request: APIRequestContext,
  runId: number,
  summary: string,
) {
  await ok(
    request.post(`/api/runs/${String(runId)}/finish`, {
      data: { outcome: "finished", summary },
    }),
  );
}
