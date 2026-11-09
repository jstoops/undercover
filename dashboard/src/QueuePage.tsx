import { useState } from "react";
import { Link } from "react-router";
import { STATUSES, STATUS_LABELS, paths, type Status } from "./api";
import { DecisionBadge, StatusBadge } from "./Badges";
import { date, humanize, money } from "./format";
import { useApi } from "./useApi";

export function QueuePage() {
  const { data: claims, error } = useApi(paths.claims);
  const [filter, setFilter] = useState<Status | null>(null);
  const shown = (claims ?? []).filter(
    (claim) => filter === null || claim.status === filter,
  );

  return (
    <section>
      <h1>Claims queue</h1>
      {error && (
        <p role="alert" className="alert">
          The queue could not be loaded: {error}
        </p>
      )}
      <div className="counts" role="group" aria-label="Claims by status">
        {STATUSES.map((status) => (
          <button
            key={status}
            type="button"
            className={`count status-${status}`}
            aria-pressed={filter === status}
            onClick={() => {
              setFilter(filter === status ? null : status);
            }}
          >
            <span className="count-label">{STATUS_LABELS[status]}</span>{" "}
            <span className="count-number">
              {(claims ?? []).filter((claim) => claim.status === status).length}
            </span>
          </button>
        ))}
      </div>
      <div className="panel table-panel">
        <table>
          <thead>
            <tr>
              <th scope="col">Claim</th>
              <th scope="col">Customer</th>
              <th scope="col">What happened</th>
              <th scope="col" className="number">
                Claimed
              </th>
              <th scope="col">Status and decision</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((claim) => (
              <tr key={claim.claim_id}>
                <td className="nowrap">
                  <Link to={`/claims/${claim.claim_id}`} className="mono">
                    {claim.claim_id}
                  </Link>
                  <span className="secondary mono">
                    {date(claim.submitted_on)}
                  </span>
                </td>
                <td>{claim.customer_name}</td>
                <td>
                  <span className="eyebrow">{humanize(claim.claim_type)}</span>
                  {claim.summary}
                </td>
                <td className="number">{money(claim.amount_claimed)}</td>
                <td>
                  <div className="stack">
                    <StatusBadge status={claim.status} />
                    {claim.decision && (
                      <span className="nowrap">
                        <DecisionBadge decision={claim.decision} />
                        {claim.decision === "approve" &&
                          claim.payout !== null && (
                            <span className="mono payout">
                              {money(claim.payout)}
                            </span>
                          )}
                      </span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
