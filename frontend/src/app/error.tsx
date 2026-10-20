"use client";

export default function ErrorPage({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <section className="section" style={{ paddingTop: 64 }}>
      <div className="notice">
        <h3>Something went wrong</h3>
        <p>{error.message || "Unexpected error."}</p>
        <p style={{ marginTop: 16 }}>
          <button className="btn" onClick={reset}>
            Try again
          </button>
        </p>
      </div>
    </section>
  );
}
