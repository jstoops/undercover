import { useState, type SyntheticEvent } from "react";
import { paths, postJson, type Claim } from "./api";
import { DecisionBadge } from "./Badges";
import { dateTime, money } from "./format";
import { useApi } from "./useApi";

interface Props {
  claim: Claim;
  onSignedOff: () => void;
}

export function DecisionPanel({ claim, onSignedOff }: Readonly<Props>) {
  const { decision } = claim;
  return (
    <section className="panel" aria-labelledby="decision-heading">
      <h2 id="decision-heading">The agent's decision</h2>
      {decision === null ? (
        <p>
          {claim.status === "in_progress"
            ? "The agent is working on this claim."
            : "The agent hasn't decided this claim yet."}
        </p>
      ) : (
        <>
          <p className="decision-line">
            <DecisionBadge decision={decision.decision} />
            {decision.decision === "approve" && (
              <span className="mono payout-large">
                {money(decision.payout)}
              </span>
            )}
          </p>
          <blockquote className="quote">{decision.reason}</blockquote>
          <dl className="facts">
            <div>
              <dt>Policy section</dt>
              <dd>{decision.policy_section}</dd>
            </div>
            <div>
              <dt>Decided</dt>
              <dd className="mono">{dateTime(decision.decided_at)}</dd>
            </div>
          </dl>
          <PaymentState claim={claim} onSignedOff={onSignedOff} />
        </>
      )}
    </section>
  );
}

function PaymentState({ claim, onSignedOff }: Readonly<Props>) {
  const { payment, sign_off: signOff } = claim;
  return (
    <>
      {signOff && (
        <p>
          Signed off by {signOff.handler_name} on{" "}
          <span className="mono">{dateTime(signOff.signed_off_at)}</span>.
        </p>
      )}
      {payment && (
        <p className="paid">
          Paid <span className="mono">{money(payment.amount)}</span> on{" "}
          <span className="mono">{dateTime(payment.paid_at)}</span>.
        </p>
      )}
      {claim.status === "awaiting_sign_off" && (
        <>
          <p className="alert">
            The payment is held until a handler signs off, because the payout is
            over $1,000.
          </p>
          <SignOffForm claimId={claim.claim_id} onSignedOff={onSignedOff} />
        </>
      )}
      {claim.status === "decided" &&
        claim.decision?.decision === "approve" &&
        !payment && <p>Not paid yet.</p>}
    </>
  );
}

function SignOffForm({
  claimId,
  onSignedOff,
}: Readonly<{ claimId: string; onSignedOff: () => void }>) {
  const { data: handlers } = useApi(paths.handlers, false);
  const [handlerId, setHandlerId] = useState("");
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  async function signOff(event: SyntheticEvent) {
    event.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      await postJson(paths.signOff(claimId), { handler_id: handlerId });
      onSignedOff();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="sign-off"
      onSubmit={(event) => {
        void signOff(event);
      }}
    >
      <label htmlFor="handler">Handler</label>
      <select
        id="handler"
        value={handlerId}
        onChange={(event) => {
          setHandlerId(event.target.value);
        }}
      >
        <option value="">Choose a handler</option>
        {handlers?.map((handler) => (
          <option key={handler.handler_id} value={handler.handler_id}>
            {handler.name}
          </option>
        ))}
      </select>
      <button type="submit" disabled={busy || handlerId === ""}>
        Sign off and pay
      </button>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
    </form>
  );
}
