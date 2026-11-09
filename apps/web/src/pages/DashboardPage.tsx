import { Link } from "react-router-dom";

export default function DashboardPage() {
  return (
    <div className="site-page">
      <div className="site-page-heading">
        <span className="site-eyebrow">YOUR CARE</span>
        <h1>A simpler way to manage your eye care.</h1>
        <p>
          Find the right appointment, explore clinics, and manage
          your care in one place.
        </p>
      </div>

      <section className="site-feature">
        <div>
          <span className="site-eyebrow">GET STARTED</span>
          <h2>Need to book a visit?</h2>
          <p>
            Tell our booking assistant what you need, and it will
            help you find a suitable appointment.
          </p>

          <Link className="site-primary-link" to="/assistant">
            Find an appointment
            <span aria-hidden="true"> →</span>
          </Link>
        </div>

        <div className="site-feature-symbol" aria-hidden="true">
          01
        </div>
      </section>

      <div className="site-section-heading">
        <h2>Quick access</h2>
        <p>Everything you need, without the extra steps.</p>
      </div>

      <div className="site-quick-grid">
        <Link to="/appointments" className="site-quick-link">
          <span className="site-quick-number">01 / APPOINTMENTS</span>
          <h3>My appointments</h3>
          <p>Review your upcoming visits and appointment history.</p>
          <span className="site-quick-arrow" aria-hidden="true">↗</span>
        </Link>

        <Link to="/clinics" className="site-quick-link">
          <span className="site-quick-number">02 / LOCATIONS</span>
          <h3>Explore clinics</h3>
          <p>Find clinic locations, services, and helpful information.</p>
          <span className="site-quick-arrow" aria-hidden="true">↗</span>
        </Link>
      </div>
    </div>
  );
}