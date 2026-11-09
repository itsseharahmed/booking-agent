export default function ClinicsPage() {
  return (
    <div className="site-page">
      <div className="site-page-heading">
        <span className="site-eyebrow">OUR LOCATIONS</span>
        <h1>Find a clinic</h1>
        <p>
          Explore locations, appointment services, and clinic details.
        </p>
      </div>

      <section className="site-empty-state">
        <span className="site-eyebrow">COMING NEXT</span>
        <h2>Clinic directory</h2>
        <p>
          Clinic information will appear here when we connect
          the existing backend clinic endpoints.
        </p>
      </section>
    </div>
  );
}