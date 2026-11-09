export default function AppointmentsPage() {
  return (
    <div className="site-page">
      <div className="site-page-heading">
        <span className="site-eyebrow">YOUR VISITS</span>
        <h1>My appointments</h1>
        <p>Keep track of your upcoming and previous visits.</p>
      </div>

      <section className="site-empty-state">
        <span className="site-eyebrow">COMING NEXT</span>
        <h2>Appointment management</h2>
        <p>
          Your booked appointments and cancellation options
          will appear here after the appointment API is connected.
        </p>
      </section>
    </div>
  );
}