import { Link, useParams } from "react-router";
import { paths } from "./api";
import { StatusBadge } from "./Badges";
import { ClaimDetails, CustomerPanel, PolicyPanel } from "./ClaimDetails";
import { DecisionPanel } from "./DecisionPanel";
import { humanize } from "./format";
import { SectionsRead } from "./SectionsRead";
import { StepList } from "./StepList";
import { useApi } from "./useApi";

export function ClaimPage() {
  const { claimId = "" } = useParams();
  const { data: claim, error, reload } = useApi(paths.claim(claimId));
  const { data: steps } = useApi(paths.steps(claimId));
  const { data: policy } = useApi(
    claim ? paths.policy(claim.policy_id) : null,
    false,
  );
  const { data: customer } = useApi(
    claim ? paths.customer(claim.customer_id) : null,
    false,
  );

  return (
    <section>
      <Link to="/" className="back">
        Back to the queue
      </Link>
      <div className="claim-header">
        <h1 className="mono">{claimId}</h1>
        {claim && <StatusBadge status={claim.status} />}
      </div>
      {error && !claim && (
        <p role="alert" className="alert">
          This claim could not be loaded: {error}
        </p>
      )}
      {claim && (
        <>
          <p className="claim-summary">
            <span className="eyebrow">{humanize(claim.claim_type)}</span>
            {claim.summary}
          </p>
          <div className="claim-grid">
            <div className="claim-side">
              <DecisionPanel claim={claim} onSignedOff={reload} />
              <SectionsRead steps={steps ?? []} />
              <StepList steps={steps ?? []} />
            </div>
            <div className="claim-main">
              <ClaimDetails claim={claim} />
              {policy && <PolicyPanel policy={policy} />}
              {customer && <CustomerPanel customer={customer} />}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
