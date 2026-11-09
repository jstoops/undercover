import { useParams } from "react-router";

export function ClaimPage() {
  const { claimId = "" } = useParams();

  return (
    <section>
      <h1 className="mono">{claimId}</h1>
    </section>
  );
}
