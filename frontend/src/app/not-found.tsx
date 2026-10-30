import Link from "next/link";

export default function NotFound() {
  return (
    <section className="section" style={{ paddingTop: 64 }}>
      <div className="notice">
        <h3>Not found</h3>
        <p>
          That trial site does not exist.{" "}
          <Link href="/" style={{ color: "var(--purple)", fontWeight: 600 }}>
            Back to the dashboard
          </Link>
        </p>
      </div>
    </section>
  );
}
