import { NavLink, Outlet } from "react-router-dom";
import "../styles/layout.css";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const navigation = [
  { label: "Overview", path: "/" },
  { label: "Book appointment", path: "/assistant" },
  { label: "My appointments", path: "/appointments" },
  { label: "Clinics", path: "/clinics" },
];

export default function AppLayout() {
    const { logout } = useAuth();
    const navigate = useNavigate();

    function handleLogout() {
    logout();
    navigate("/login", { replace: true });
    }
  return (
    <div className="site-shell">
      <aside className="site-sidebar">
        <div className="site-brand">
          <div className="site-brand-mark" aria-hidden="true">
            O
          </div>

          <div>
            <strong>Optometry</strong>
            <span>Patient portal</span>
          </div>
        </div>

        <div className="site-navigation-heading">YOUR SPACE</div>

        <nav className="site-navigation" aria-label="Main navigation">
          {navigation.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) =>
                `site-nav-link${isActive ? " is-active" : ""}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="site-sidebar-footer">
          <span>Thoughtful care, made simple.</span>
        </div>
      </aside>

      <div className="site-workspace">
        <header className="site-topbar">
          <span className="site-topbar-label">PATIENT EXPERIENCE</span>
            <button type="button" className="site-logout" onClick={handleLogout}>
                Sign out
            </button>
        </header>

        <div className="site-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}