/** Same two-panel shell as the sign-in page, so it never flashes unstyled while the demo accounts load. */
export default function LoginLoading() {
  return (
    <main className="login" aria-busy="true">
      <section className="login__story" />
      <section className="login__auth" />
    </main>
  );
}
