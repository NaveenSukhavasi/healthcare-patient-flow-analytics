import { useEffect, useState } from 'react'
import './App.css'

type Manifest = {
  patient_count: number
  encounter_count: number
  hospital_count: number
  hours: number
  generator_version: number
}

type Hospital = {
  hospital_id: string
  presentation_count: string
  median_waiting_time_minutes: string
  median_ed_length_of_stay_minutes: string
  four_hour_completion_rate: string
  admission_rate: string
}

type Daily = {
  hospital_id: string
  arrival_date_utc: string
  presentation_count: string
  median_waiting_time_minutes: string
  four_hour_completion_rate: string
}

type Representation = {
  available: boolean
  reason?: string
  overlapping_arrivals?: number
  eligible_seven_day_followups?: number
  apparent_seven_day_returns?: number
  apparent_return_rate?: number | null
}

type EventRecord = {
  event_id: string
  encounter_id: string
  hospital_id: string
  occurred_at: string
  event_type: string
}

const staticDemo = import.meta.env.VITE_STATIC_DEMO === '1'
const dataUrl = (name: string) =>
  staticDemo ? `${import.meta.env.BASE_URL}demo/${name}.json` : `/api/${name}`

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`)
  return response.json() as Promise<T>
}

function percent(value: string | number | null | undefined): string {
  if (value == null) return '—'
  return `${(Number(value) * 100).toFixed(1)}%`
}

function App() {
  const [manifest, setManifest] = useState<Manifest | null>(null)
  const [hospitals, setHospitals] = useState<Hospital[]>([])
  const [daily, setDaily] = useState<Daily[]>([])
  const [representation, setRepresentation] =
    useState<Representation | null>(null)
  const [events, setEvents] = useState<EventRecord[]>([])
  const [selected, setSelected] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      getJson<Manifest>(dataUrl('manifest')),
      getJson<Hospital[]>(dataUrl('hospitals')),
      getJson<Daily[]>(dataUrl('daily')),
      getJson<Representation>(dataUrl('representation')),
    ])
      .then(([run, hospitalRows, dailyRows, audit]) => {
        setManifest(run)
        setHospitals(hospitalRows)
        setDaily(dailyRows)
        setRepresentation(audit)
      })
      .catch((cause: unknown) => setError(String(cause)))

    const refreshEvents = () => {
      getJson<EventRecord[]>(staticDemo ? dataUrl('events') : '/api/events?limit=12')
        .then(setEvents)
        .catch((cause: unknown) => setError(String(cause)))
    }
    refreshEvents()
    if (staticDemo) return
    const timer = window.setInterval(refreshEvents, 3000)
    return () => window.clearInterval(timer)
  }, [])

  const maxPresentations = Math.max(
    1,
    ...hospitals.map((row) => Number(row.presentation_count)),
  )
  const shownDaily = daily
    .filter((row) => !selected || row.hospital_id === selected)
    .slice()
    .reverse()
    .slice(0, 14)

  return (
    <>
      <header className="site-header">
        <div className="container">
          <p className="eyebrow">SYNTHETIC HEALTHCARE • PORTFOLIO DEMO</p>
          <h1>Emergency department patient flow</h1>
          <p>Eight fictional hospitals. Generated events, operational KPIs,
            and seven-day return analysis.</p>
        </div>
      </header>

      <main className="container">
        {error && <p role="alert" className="error">{error}</p>}

        <section className="cards" aria-label="Run summary">
          <div className="card"><span>Patients</span>
            <strong>{manifest?.patient_count.toLocaleString() ?? '—'}</strong>
          </div>
          <div className="card"><span>Encounters</span>
            <strong>{manifest?.encounter_count.toLocaleString() ?? '—'}</strong>
          </div>
          <div className="card"><span>Hospitals</span>
            <strong>{manifest?.hospital_count ?? '—'}</strong>
          </div>
          <div className="card"><span>Run duration</span>
            <strong>{manifest ? `${manifest.hours / 24} days` : '—'}</strong>
          </div>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">OPERATIONS</p>
              <h2>Hospital performance</h2>
            </div>
            <span className="badge">Generator v{manifest?.generator_version ?? '—'}</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Hospital</th><th>Presentations</th>
                  <th>Median wait</th><th>Median stay</th>
                  <th>Four-hour completion</th><th>Admission rate</th>
                </tr>
              </thead>
              <tbody>
                {hospitals.map((row) => (
                  <tr key={row.hospital_id}>
                    <td><strong>{row.hospital_id}</strong></td>
                    <td>
                      {row.presentation_count}
                      <div className="bar"><span style={{
                        width: `${100 * Number(row.presentation_count) / maxPresentations}%`,
                      }} /></div>
                    </td>
                    <td>{row.median_waiting_time_minutes} min</td>
                    <td>{row.median_ed_length_of_stay_minutes} min</td>
                    <td>{percent(row.four_hour_completion_rate)}</td>
                    <td>{percent(row.admission_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <div className="two-columns">
          <section className="panel">
            <p className="eyebrow">FOLLOW-UP</p>
            <h2>Seven-day re-presentation</h2>
            {representation?.available ? (
              <>
                <div className="highlight">
                  {percent(representation.apparent_return_rate)}
                </div>
                <p>
                  {representation.apparent_seven_day_returns} returns among{' '}
                  {representation.eligible_seven_day_followups} eligible visits.
                </p>
                <p>Overlapping arrivals: {representation.overlapping_arrivals}</p>
              </>
            ) : (
              <p>{representation?.reason ?? 'Loading audit…'}</p>
            )}
          </section>

          <section className="panel">
            <p className="eyebrow">EVENTS</p>
            <h2>{staticDemo ? 'Recent generated events' : 'Recent events'}</h2>
            <div className="event-list">
              {events.map((event) => (
                <div className="event" key={event.event_id}>
                  <span className="event-type">{event.event_type.replaceAll('_', ' ')}</span>
                  <span>{event.hospital_id} · {event.encounter_id}</span>
                  <time>{new Date(event.occurred_at).toLocaleString()}</time>
                </div>
              ))}
            </div>
          </section>
        </div>

        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">TRENDS</p>
              <h2>Recent daily results</h2>
            </div>
            <label>
              Hospital{' '}
              <select value={selected} onChange={(event) => setSelected(event.target.value)}>
                <option value="">All hospitals</option>
                {hospitals.map((row) => (
                  <option key={row.hospital_id} value={row.hospital_id}>
                    {row.hospital_id}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date UTC</th><th>Hospital</th><th>Presentations</th>
                  <th>Median wait</th><th>Four-hour completion</th>
                </tr>
              </thead>
              <tbody>
                {shownDaily.map((row) => (
                  <tr key={`${row.arrival_date_utc}-${row.hospital_id}`}>
                    <td>{row.arrival_date_utc}</td>
                    <td>{row.hospital_id}</td>
                    <td>{row.presentation_count}</td>
                    <td>{row.median_waiting_time_minutes} min</td>
                    <td>{percent(row.four_hour_completion_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      <footer className="container">
        Fictional data for software and data-science demonstration.
        Not clinically validated or medical advice.
      </footer>
    </>
  )
}

export default App
