import {
  Activity,
  AlertTriangle,
  Bell,
  Brain,
  CircleAlert,
  Clock3,
  Database,
  FileSearch,
  Home,
  Menu,
  Network,
  Search,
  Settings,
  Shield,
  Terminal,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import "./App.css";
import { api, type Incident, type Project } from "./api/client";
import InvestigationPage from "./components/InvestigationPage";

function App() {
  const [mobileMenu, setMobileMenu] = useState(false);
  const [active, setActive] = useState("Overview");

  const [projects, setProjects] = useState<Project[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const navigation = [
    { name: "Overview", icon: Home },
    { name: "Log Explorer", icon: Terminal },
    { name: "Detections", icon: CircleAlert },
    { name: "Anomalies", icon: Activity },
    { name: "Investigations", icon: Brain },
    { name: "Correlations", icon: Network },
    { name: "Intelligence", icon: Search },
    { name: "Reports", icon: FileSearch },
    { name: "Alerts", icon: Bell },
    { name: "Settings", icon: Settings },
  ];

  useEffect(() => {
    let mounted = true;

    async function loadDashboard() {
      try {
        setLoading(true);
        setError(null);

        const [projectData, incidentData] = await Promise.all([
          api.projects.list(),
          api.incidents.list(),
        ]);

        if (!mounted) return;

        setProjects(
          Array.isArray(projectData)
            ? projectData
            : [projectData],
        );

        setIncidents(
          Array.isArray(incidentData)
            ? incidentData
            : [incidentData],
        );
      } catch (err) {
        if (!mounted) return;

        setError(
          err instanceof Error
            ? err.message
            : "Unable to connect to AegisAI API.",
        );
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadDashboard();

    return () => {
      mounted = false;
    };
  }, []);

  const criticalCount = useMemo(
    () =>
      incidents.filter(
        (incident) =>
          incident.severity?.toLowerCase() === "critical",
      ).length,
    [incidents],
  );

  const openCount = useMemo(
    () =>
      incidents.filter(
        (incident) =>
          incident.status?.toLowerCase() === "open",
      ).length,
    [incidents],
  );

  const resolvedCount = useMemo(
    () =>
      incidents.filter(
        (incident) =>
          incident.status?.toLowerCase() === "resolved",
      ).length,
    [incidents],
  );

  const activeIncident = incidents[0];

  const handleNavigation = (name: string) => {
    setActive(name);
    setMobileMenu(false);
  };

  return (
    <div className="app">
      {mobileMenu && (
        <div
          className="mobile-overlay"
          onClick={() => setMobileMenu(false)}
        />
      )}

      <aside
        className={`sidebar ${
          mobileMenu ? "sidebar-open" : ""
        }`}
      >
        <div className="sidebar-brand">
          <div className="logo-mark">
            <span>AI</span>
          </div>

          <div className="brand-copy">
            <div>AI Log</div>
            <div>Detective</div>
          </div>

          <button
            className="mobile-close"
            onClick={() => setMobileMenu(false)}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        <nav className="navigation">
          {navigation.map((item) => {
            const Icon = item.icon;
            const selected = active === item.name;

            return (
              <button
                key={item.name}
                className={`nav-item ${
                  selected ? "selected" : ""
                }`}
                onClick={() =>
                  handleNavigation(item.name)
                }
              >
                <Icon size={17} strokeWidth={1.7} />

                <span>{item.name}</span>

                {item.name === "Alerts" &&
                  criticalCount > 0 && (
                    <span className="alert-count">
                      {criticalCount}
                    </span>
                  )}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-status">
          <div className="status-heading">
            SYSTEM STATUS
          </div>

          <div className="system-state">
            <span className="status-dot" />
            <span>
              {error ? "API Error" : "Operational"}
            </span>
          </div>

          <div className="status-metrics">
            <div>
              <span>Projects</span>
              <strong>{projects.length}</strong>
            </div>

            <div>
              <span>Open Incidents</span>
              <strong>{openCount}</strong>
            </div>

            <div>
              <span>Critical</span>
              <strong>{criticalCount}</strong>
            </div>
          </div>
        </div>

        <div className="sidebar-version">
          AegisAI Reliability Engine v0.1.0
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="mobile-menu"
              onClick={() => setMobileMenu(true)}
              aria-label="Open navigation"
            >
              <Menu size={20} />
            </button>

            <div>
              <div className="breadcrumb">
                OPERATIONS CENTER
              </div>

              <h1>{active}</h1>

              <p>
                AI-powered production reliability intelligence
              </p>
            </div>
          </div>

          <div className="topbar-actions">
            <button className="date-button">
              <span>Production</span>
              <Clock3 size={15} />
            </button>

            <button className="export-button">
              <FileSearch size={15} />
              Export Report
            </button>

            <button className="notification-button">
              <Bell size={17} />

              {criticalCount > 0 && (
                <span>{criticalCount}</span>
              )}
            </button>

            <div className="profile">DK</div>
          </div>
        </header>

        {error && (
          <div className="api-error">
            <CircleAlert size={17} />

            <div>
              <strong>Backend connection error</strong>
              <span>{error}</span>
            </div>
          </div>
        )}

        {loading ? (
          <LoadingState />
        ) : active === "Investigations" ? (
          <InvestigationPage incident={activeIncident} />
        ) : (
          <>
            <section className="stats-grid">
              <StatCard
                title="PROJECTS"
                value={String(projects.length)}
                change="LIVE"
                subtitle="from PostgreSQL"
                icon={<Database size={21} />}
                tone="cream"
              />

              <StatCard
                title="INCIDENTS"
                value={String(incidents.length)}
                change="LIVE"
                subtitle="from API"
                icon={<Activity size={21} />}
                tone="blush"
              />

              <StatCard
                title="CRITICAL"
                value={String(criticalCount)}
                change="LIVE"
                subtitle="active severity"
                icon={<AlertTriangle size={21} />}
                tone="mauve"
              />

              <StatCard
                title="OPEN"
                value={String(openCount)}
                change="LIVE"
                subtitle="requiring attention"
                icon={<Search size={21} />}
                tone="lavender"
              />

              <StatCard
                title="API STATUS"
                value="HEALTHY"
                change="LIVE"
                subtitle="FastAPI"
                icon={<Shield size={21} />}
                tone="cream"
              />
            </section>

            <section className="dashboard-grid">
              <div className="panel detections-chart">
                <PanelTitle
                  title="Production Incident"
                  subtitle="Live incident intelligence"
                  action="LIVE"
                />

                {activeIncident ? (
                  <div className="incident-focus">
                    <div className="incident-focus-header">
                      <div>
                        <span className="incident-label">
                          ACTIVE INCIDENT
                        </span>

                        <h3>
                          {activeIncident.title ||
                            "Untitled incident"}
                        </h3>

                        <p>
                          {activeIncident.description ||
                            "No description provided."}
                        </p>
                      </div>

                      <SeverityBadge
                        severity={
                          activeIncident.severity ||
                          "info"
                        }
                      />
                    </div>

                    <div className="incident-meta">
                      <MetaItem
                        label="STATUS"
                        value={
                          activeIncident.status || "unknown"
                        }
                      />

                      <MetaItem
                        label="PROJECT"
                        value={
                          projects.find(
                            (project) =>
                              project.id ===
                              activeIncident.project_id,
                          )?.name || "Unknown"
                        }
                      />

                      <MetaItem
                        label="STARTED"
                        value={formatDate(
                          activeIncident.started_at,
                        )}
                      />

                      <MetaItem
                        label="INCIDENT ID"
                        value={activeIncident.id}
                        mono
                      />
                    </div>
                  </div>
                ) : (
                  <EmptyState
                    title="No incidents"
                    description="AegisAI currently has no incidents."
                  />
                )}
              </div>

              <div className="panel severity-panel">
                <PanelTitle
                  title="Incident Distribution"
                  subtitle={`${incidents.length} total incidents`}
                />

                <div className="severity-content">
                  <div className="donut">
                    <div className="donut-hole">
                      <strong>{incidents.length}</strong>
                      <span>Incidents</span>
                    </div>
                  </div>

                  <div className="severity-list">
                    <SeverityRow
                      label="Critical"
                      count={criticalCount}
                      percent={percentage(
                        criticalCount,
                        incidents.length,
                      )}
                      tone="blush"
                    />

                    <SeverityRow
                      label="Open"
                      count={openCount}
                      percent={percentage(
                        openCount,
                        incidents.length,
                      )}
                      tone="mauve"
                    />

                    <SeverityRow
                      label="Resolved"
                      count={resolvedCount}
                      percent={percentage(
                        resolvedCount,
                        incidents.length,
                      )}
                      tone="cream"
                    />
                  </div>
                </div>
              </div>

              <div className="panel sources-panel">
                <PanelTitle
                  title="Connected Projects"
                  subtitle="Live backend resources"
                />

                {projects.length === 0 ? (
                  <EmptyState
                    title="No projects"
                    description="No projects are currently available."
                  />
                ) : (
                  <div className="project-list">
                    {projects.map((project) => (
                      <div
                        className="project-card"
                        key={project.id}
                      >
                        <div className="project-icon">
                          <Database size={17} />
                        </div>

                        <div>
                          <strong>
                            {project.name || "Unnamed project"}
                          </strong>

                          <span>
                            {project.description ||
                              "No description"}
                          </span>

                          <code>
                            {String(
                              project.slug || project.id,
                            )}
                          </code>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="panel recent-panel">
                <PanelTitle
                  title="Recent Incidents"
                  subtitle="Live data from FastAPI"
                  action="LIVE"
                />

                <div className="table">
                  <div className="table-header">
                    <span>TIME</span>
                    <span>SEVERITY</span>
                    <span>STATUS</span>
                    <span>INCIDENT</span>
                    <span>PROJECT</span>
                  </div>

                  {incidents.map((incident) => (
                    <div
                      className="table-row"
                      key={incident.id}
                    >
                      <span className="mono">
                        {formatTime(incident.created_at)}
                      </span>

                      <span>
                        <SeverityBadge
                          severity={
                            incident.severity || "info"
                          }
                        />
                      </span>

                      <span
                        className={`detection-status ${
                          incident.status === "open"
                            ? "status-investigating"
                            : "status-new"
                        }`}
                      >
                        {incident.status || "unknown"}
                      </span>

                      <span className="detection-name">
                        {incident.title ||
                          "Untitled incident"}
                      </span>

                      <span>
                        {projects.find(
                          (project) =>
                            project.id ===
                            incident.project_id,
                        )?.name || "Unknown"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="panel heatmap-panel">
                <PanelTitle
                  title="Investigation Pipeline"
                  subtitle="AegisAI reliability workflow"
                />

                <div className="pipeline">
                  <PipelineStep
                    number="01"
                    title="Detect"
                    description="Identify failure signals"
                    icon={<CircleAlert size={16} />}
                  />

                  <PipelineStep
                    number="02"
                    title="Correlate"
                    description="Connect related events"
                    icon={<Network size={16} />}
                  />

                  <PipelineStep
                    number="03"
                    title="RCA"
                    description="Analyze root cause"
                    icon={<Brain size={16} />}
                  />

                  <PipelineStep
                    number="04"
                    title="Localize"
                    description="Find affected code"
                    icon={<Search size={16} />}
                  />

                  <PipelineStep
                    number="05"
                    title="Repair"
                    description="Generate remediation"
                    icon={<Terminal size={16} />}
                  />
                </div>
              </div>

              <div className="panel alerts-panel">
                <PanelTitle
                  title="Current Alerts"
                  subtitle="Events requiring attention"
                />

                {incidents.filter(
                  (incident) =>
                    incident.status === "open",
                ).length === 0 ? (
                  <EmptyState
                    title="No active alerts"
                    description="The system has no open incidents."
                  />
                ) : (
                  <div className="alert-list">
                    {incidents
                      .filter(
                        (incident) =>
                          incident.status === "open",
                      )
                      .map((incident) => (
                        <div
                          className="alert-card"
                          key={incident.id}
                        >
                          <div className="alert-icon">
                            <AlertTriangle size={17} />
                          </div>

                          <div className="alert-content">
                            <strong>
                              {incident.title}
                            </strong>

                            <span>
                              {incident.description}
                            </span>
                          </div>

                          <time>
                            {formatTime(
                              incident.started_at,
                            )}
                          </time>
                        </div>
                      ))}
                  </div>
                )}
              </div>

              <div className="panel log-stream">
                <PanelTitle
                  title="AegisAI Engine"
                  subtitle="Backend capabilities"
                  live
                />

                <div className="logs">
                  <StatusLine
                    label="Evidence aggregation"
                    status="READY"
                  />

                  <StatusLine
                    label="Root cause analysis"
                    status="READY"
                  />

                  <StatusLine
                    label="Code localization"
                    status="READY"
                  />

                  <StatusLine
                    label="Repair validation"
                    status="READY"
                  />

                  <StatusLine
                    label="GitHub remediation"
                    status="READY"
                  />
                </div>
              </div>
            </section>
          </>
        )}

        <footer className="footer">
          <span>AegisAI Reliability Engine</span>
          <span>AI-powered production intelligence</span>
          <span>v0.1.0</span>
        </footer>
      </main>
    </div>
  );
}

function StatCard({
  title,
  value,
  change,
  subtitle,
  icon,
  tone,
}: {
  title: string;
  value: string;
  change: string;
  subtitle: string;
  icon: React.ReactNode;
  tone: "cream" | "blush" | "mauve" | "lavender";
}) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${tone}`}>
        {icon}
      </div>

      <div className="stat-title">{title}</div>

      <div className="stat-value">{value}</div>

      <div className="stat-change">
        <span>{change}</span> {subtitle}
      </div>
    </div>
  );
}

function PanelTitle({
  title,
  subtitle,
  action,
  live,
}: {
  title: string;
  subtitle?: string;
  action?: string;
  live?: boolean;
}) {
  return (
    <div className="panel-title">
      <div>
        <h2>{title}</h2>

        {subtitle && <p>{subtitle}</p>}
      </div>

      <div className="panel-action-area">
        {live && (
          <span className="live-indicator">
            <i />
            LIVE
          </span>
        )}

        {action && (
          <button className="panel-action">
            {action}
          </button>
        )}
      </div>
    </div>
  );
}

function SeverityRow({
  label,
  count,
  percent,
  tone,
}: {
  label: string;
  count: number;
  percent: string;
  tone: string;
}) {
  return (
    <div className="severity-row">
      <div className={`severity-dot ${tone}`} />

      <div>
        <strong>{label}</strong>

        <span>
          {count} ({percent})
        </span>
      </div>
    </div>
  );
}

function SeverityBadge({
  severity,
}: {
  severity: string;
}) {
  return (
    <span
      className={`severity-badge severity-${severity.toLowerCase()}`}
    >
      {severity.toUpperCase()}
    </span>
  );
}

function MetaItem({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="meta-item">
      <span>{label}</span>

      <strong className={mono ? "mono" : ""}>
        {value}
      </strong>
    </div>
  );
}

function PipelineStep({
  number,
  title,
  description,
  icon,
}: {
  number: string;
  title: string;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="pipeline-step">
      <div className="pipeline-number">{number}</div>

      <div className="pipeline-icon">{icon}</div>

      <div>
        <strong>{title}</strong>
        <span>{description}</span>
      </div>
    </div>
  );
}

function StatusLine({
  label,
  status,
}: {
  label: string;
  status: string;
}) {
  return (
    <div className="status-line">
      <span className="status-line-dot" />
      <span>{label}</span>
      <strong>{status}</strong>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="loading-state">
      <div className="loading-spinner" />

      <h2>Loading production intelligence</h2>

      <p>
        Connecting to the AegisAI reliability engine...
      </p>
    </div>
  );
}

function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="empty-state">
      <Database size={20} />

      <strong>{title}</strong>

      <span>{description}</span>
    </div>
  );
}

function formatDate(value?: string | null): string {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function formatTime(value?: string | null): string {
  if (!value) return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function percentage(
  value: number,
  total: number,
): string {
  if (total === 0) return "0%";

  return `${Math.round(
    (value / total) * 100,
  )}%`;
}

export default App;


