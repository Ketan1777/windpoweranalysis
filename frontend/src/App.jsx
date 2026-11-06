import { useEffect, useState } from "react";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "";

function formatNumber(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) {
    return "—";
  }

  return Number(value).toLocaleString("en-GB", {
    maximumFractionDigits: 2,
  });
}

function formatDateTime(value) {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/London",
  });
}

function MetricCard({ title, value, unit, description }) {
  return (
    <article className="metric-card">
      <p className="metric-title">{title}</p>

      <div className="metric-value">
        {value}
        {unit && <span className="metric-unit">{unit}</span>}
      </div>

      <p className="metric-description">{description}</p>
    </article>
  );
}

function App() {
  const [startDate, setStartDate] = useState("2026-01-01");
  const [endDate, setEndDate] = useState("2026-01-31");

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadAnalysis() {
    if (startDate > endDate) {
      setError("The start date must be before or equal to the end date.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
      });

      const response = await fetch(
        `${API_URL}/api/wind/analysis?${params.toString()}`
      );

      if (!response.ok) {
        const message = await response.text();
        throw new Error(
          `Backend returned ${response.status}: ${message}`
        );
      }

      const result = await response.json();

      setData(result);
    } catch (err) {
      setError(
        err.message ||
          "Unable to load wind-generation analysis. Check the backend."
      );
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAnalysis();

    // Initial load only. Filters are applied through the button.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const metrics = data?.metrics || {};
  const records = data?.records || [];

  const chartData = records.map((record) => ({
    ...record,
    timeLabel: formatDateTime(record.startTime),
  }));

  const hasRecords = records.length > 0;

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/">
          <span className="brand-icon">W</span>

          <span>
            Wind<span className="brand-accent">Analytics</span>
          </span>
        </a>

        <div className="topbar-right">
          <span className="status-dot" />
          <span>January 2026 Analysis</span>
        </div>
      </header>

      <section className="page-content">
        <div className="hero">
          <div>
            <p className="eyebrow">ENERGY INTELLIGENCE</p>

            <h1>
              Wind Generation
              <br />
              <span>Forecast Analytics</span>
            </h1>

            <p className="hero-description">
              Compare forecasted and actual UK wind generation
              to understand forecast accuracy and potential
              purchasing implications.
            </p>
          </div>

          <div className="hero-badge">
            <span className="badge-symbol">↗</span>
            <div>
              <strong>Elexon data</strong>
              <p>UK electricity market</p>
            </div>
          </div>
        </div>

        <section className="filter-panel">
          <div className="filter-heading">
            <div>
              <h2>Analysis period</h2>
              <p>Select the period you want to inspect.</p>
            </div>
          </div>

          <form
            className="filter-form"
            onSubmit={(event) => {
              event.preventDefault();
              loadAnalysis();
            }}
          >
            <label>
              Start date
              <input
                type="date"
                value={startDate}
                min="2026-01-01"
                max="2026-12-31"
                onChange={(event) => setStartDate(event.target.value)}
              />
            </label>

            <label>
              End date
              <input
                type="date"
                value={endDate}
                min="2026-01-01"
                max="2026-12-31"
                onChange={(event) => setEndDate(event.target.value)}
              />
            </label>

            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? "Loading..." : "Run analysis"}
            </button>
          </form>
        </section>

        {error && (
          <div className="error-banner" role="alert">
            <strong>Unable to load analysis</strong>
            <p>{error}</p>
            <button onClick={loadAnalysis}>Try again</button>
          </div>
        )}

        {loading && !data && (
          <div className="state-panel">
            <div className="loader" />
            <p>Fetching wind-generation data...</p>
          </div>
        )}

        {!loading && !error && data && (
          <>
            <section className="section-heading">
              <div>
                <p className="eyebrow">PERFORMANCE OVERVIEW</p>
                <h2>Forecast accuracy</h2>
              </div>

              <span className="record-badge">
                {formatNumber(metrics.sample_count)} matched records
              </span>
            </section>

            {!hasRecords && (
              <div className="empty-banner">
                <strong>No matching records found</strong>
                <p>
                  The API did not return matched forecast and actual
                  generation records for this period. Check the backend
                  response and Elexon data integration.
                </p>
              </div>
            )}

            <section className="metrics-grid">
              <MetricCard
                title="Mean Absolute Error"
                value={formatNumber(metrics.mae)}
                unit=" MW"
                description="Average absolute forecast error. Lower is better."
              />

              <MetricCard
                title="Root Mean Squared Error"
                value={formatNumber(metrics.rmse)}
                unit=" MW"
                description="Penalizes larger forecast errors more heavily."
              />

              <MetricCard
                title="Forecast Bias"
                value={formatNumber(metrics.bias)}
                unit=" MW"
                description="Positive means overforecasting; negative means underforecasting."
              />

              <MetricCard
                title="Matched Records"
                value={formatNumber(metrics.sample_count)}
                unit=""
                description="Target periods with both forecast and actual data."
              />
            </section>

            <section className="panel chart-panel">
              <div className="panel-heading">
                <div>
                  <h2>Forecast vs. actual generation</h2>
                  <p>Wind generation measured in megawatts (MW).</p>
                </div>

                <span className="chart-period">
                  {startDate} — {endDate}
                </span>
              </div>

              {hasRecords ? (
                <div className="chart-container">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                      data={chartData}
                      margin={{
                        top: 16,
                        right: 20,
                        left: 4,
                        bottom: 12,
                      }}
                    >
                      <CartesianGrid
                        stroke="#e7edf4"
                        strokeDasharray="4 4"
                      />

                      <XAxis
                        dataKey="timeLabel"
                        tick={{ fill: "#718096", fontSize: 11 }}
                        tickLine={false}
                        axisLine={false}
                        minTickGap={50}
                      />

                      <YAxis
                        tick={{ fill: "#718096", fontSize: 11 }}
                        tickLine={false}
                        axisLine={false}
                        width={65}
                        tickFormatter={(value) =>
                          Number(value).toLocaleString("en-GB")
                        }
                      />

                      <Tooltip
                        labelFormatter={(label) => `Target: ${label}`}
                        formatter={(value, name) => [
                          `${formatNumber(value)} MW`,
                          name,
                        ]}
                        contentStyle={{
                          borderRadius: "12px",
                          border: "1px solid #e2e8f0",
                        }}
                      />

                      <Legend />

                      <Line
                        type="monotone"
                        dataKey="actualGeneration"
                        name="Actual generation"
                        stroke="#087f8c"
                        strokeWidth={2.5}
                        dot={false}
                        activeDot={{ r: 5 }}
                      />

                      <Line
                        type="monotone"
                        dataKey="forecastGeneration"
                        name="Forecast generation"
                        stroke="#7665dc"
                        strokeWidth={2.5}
                        dot={false}
                        activeDot={{ r: 5 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="chart-empty">
                  The chart will appear when matched records are available.
                </div>
              )}
            </section>

            <section className="panel table-panel">
              <div className="panel-heading">
                <div>
                  <h2>Generation records</h2>
                  <p>Inspect individual forecast and actual values.</p>
                </div>

                <span className="record-badge">
                  {records.length} records
                </span>
              </div>

              <div className="table-wrapper">
                <table>
                  <thead>
                    <tr>
                      <th>Target time</th>
                      <th>Forecast published</th>
                      <th>Forecast (MW)</th>
                      <th>Actual (MW)</th>
                      <th>Error (MW)</th>
                    </tr>
                  </thead>

                  <tbody>
                    {records.map((record, index) => (
                      <tr key={`${record.startTime}-${index}`}>
                        <td>{formatDateTime(record.startTime)}</td>

                        <td>
                          {formatDateTime(record.forecastPublishedAt)}
                        </td>

                        <td>
                          {formatNumber(record.forecastGeneration)}
                        </td>

                        <td>
                          {formatNumber(record.actualGeneration)}
                        </td>

                        <td
                          className={
                            record.error > 0
                              ? "error-positive"
                              : record.error < 0
                                ? "error-negative"
                                : ""
                          }
                        >
                          {formatNumber(record.error)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {hasRecords && (
                <p className="table-note">
                  Error = forecast generation − actual generation.
                  Positive values indicate overforecasting.
                </p>
              )}
            </section>

            <section className="insight-panel">
              <div className="insight-icon">i</div>

              <div>
                <h3>Interpreting these results</h3>

                <p>
                  Lower MAE and RMSE indicate smaller forecast errors.
                  Forecast bias reveals systematic overestimation or
                  underestimation. These metrics alone do not determine
                  how much additional electricity should be purchased;
                  that decision also depends on forecast timing,
                  demand, market prices, and the purchasing strategy.
                </p>
              </div>
            </section>

            {data.assumption && (
              <p className="assumption-note">
                Analysis assumption: {data.assumption}
              </p>
            )}
          </>
        )}

        <footer className="footer">
          <span>Wind Analytics · Full Stack SWE Challenge</span>
          <span>Data source: Elexon</span>
        </footer>
      </section>
    </main>
  );
}

export default App;