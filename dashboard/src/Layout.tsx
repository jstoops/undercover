import { NavLink, Outlet } from "react-router";

export function Layout() {
  return (
    <div className="layout">
      <header className="side-nav">
        <NavLink to="/" className="brand">
          UnderCover
        </NavLink>
        <p className="tagline">Travel insurance claims</p>
        <nav aria-label="Main">
          <ul>
            <li>
              <NavLink to="/" end>
                Queue
              </NavLink>
            </li>
            <li>
              <NavLink to="/instructions">Instructions</NavLink>
            </li>
          </ul>
        </nav>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
