import type { Claim, Customer, Policy } from "./api";
import { date, humanize, money } from "./format";

export function ClaimDetails({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <section className="panel" aria-labelledby="claim-heading">
      <h2 id="claim-heading">The claim</h2>
      <blockquote className="quote">{claim.story}</blockquote>
      <dl className="facts">
        <div>
          <dt>Customer</dt>
          <dd>{claim.customer_name}</dd>
        </div>
        <div>
          <dt>Incident</dt>
          <dd>
            <span className="mono">{date(claim.incident_date)}</span>,{" "}
            {claim.incident_location}
          </dd>
        </div>
        <div>
          <dt>Submitted</dt>
          <dd className="mono">{date(claim.submitted_on)}</dd>
        </div>
      </dl>
      <h3>Items claimed</h3>
      <table>
        <thead>
          <tr>
            <th scope="col">Item</th>
            <th scope="col">Category</th>
            <th scope="col" className="number">
              Amount
            </th>
          </tr>
        </thead>
        <tbody>
          {claim.items.map((item) => (
            <tr key={item.description}>
              <td>{item.description}</td>
              <td>{humanize(item.category)}</td>
              <td className="number">{money(item.amount)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row" colSpan={2}>
              Amount claimed
            </th>
            <td className="number">{money(claim.amount_claimed)}</td>
          </tr>
        </tfoot>
      </table>
      <h3>Documents</h3>
      {claim.documents.map((document) => (
        <article key={document.name} className="document">
          <h4>{document.name}</h4>
          <span className="eyebrow">{humanize(document.type)}</span>
          <p>{document.content}</p>
        </article>
      ))}
    </section>
  );
}

export function PolicyPanel({ policy }: Readonly<{ policy: Policy }>) {
  return (
    <section className="panel" aria-labelledby="policy-heading">
      <h2 id="policy-heading">The policy</h2>
      <dl className="facts">
        <div>
          <dt>Policy</dt>
          <dd className="mono">{policy.policy_id}</dd>
        </div>
        <div>
          <dt>Plan</dt>
          <dd>{humanize(policy.plan)}</dd>
        </div>
        <div>
          <dt>Add-ons</dt>
          <dd>
            {policy.add_ons.length
              ? policy.add_ons.map(humanize).join(", ")
              : "None"}
          </dd>
        </div>
        <div>
          <dt>Bought</dt>
          <dd>
            <span className="mono">{date(policy.purchased_on)}</span>, through{" "}
            {policy.sold_through}
          </dd>
        </div>
        <div>
          <dt>Trip</dt>
          <dd>
            {policy.trip.destination},{" "}
            <span className="mono">
              {date(policy.trip.departs_on)} to {date(policy.trip.returns_on)}
            </span>
          </dd>
        </div>
        <div>
          <dt>Trip cost</dt>
          <dd className="mono">{money(policy.trip.trip_cost)}</dd>
        </div>
        <div>
          <dt>Travelers</dt>
          <dd>{policy.travelers.join(", ")}</dd>
        </div>
      </dl>
    </section>
  );
}

export function CustomerPanel({ customer }: Readonly<{ customer: Customer }>) {
  return (
    <section className="panel" aria-labelledby="customer-heading">
      <h2 id="customer-heading">The customer</h2>
      <dl className="facts">
        <div>
          <dt>Name</dt>
          <dd>{customer.name}</dd>
        </div>
        <div>
          <dt>Customer since</dt>
          <dd className="mono">{date(customer.customer_since)}</dd>
        </div>
      </dl>
      <h3>Earlier claims</h3>
      {customer.previous_claims.length === 0 ? (
        <p>No earlier claims.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Claim</th>
                <th scope="col">Filed</th>
                <th scope="col">What happened</th>
                <th scope="col">Outcome</th>
                <th scope="col" className="number">
                  Paid
                </th>
              </tr>
            </thead>
            <tbody>
              {customer.previous_claims.map((earlier) => (
                <tr key={earlier.claim_id}>
                  <td className="mono">{earlier.claim_id}</td>
                  <td className="mono nowrap">{date(earlier.filed_on)}</td>
                  <td>
                    <span className="eyebrow">
                      {humanize(earlier.claim_type)}
                    </span>
                    {earlier.summary}
                  </td>
                  <td>{humanize(earlier.outcome)}</td>
                  <td className="number">{money(earlier.amount_paid)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
