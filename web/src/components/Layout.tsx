import { Link, Outlet } from "react-router-dom";

export function Layout() {
  return (
    <>
      <div className="synthetic-banner" role="note">
        Synthetic data — not real patients
      </div>
      <header className="app-header">
        <Link to="/" className="brand">
          Care Gap Radar
        </Link>
        <span className="tagline">Who should I call this week, and what should I say?</span>
      </header>
      <main className="container">
        <Outlet />
      </main>
    </>
  );
}
