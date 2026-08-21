import { useState } from "react";
import {
  Activity,
  AlertTriangle,
  Brain,
  CheckCircle2,
  ChevronRight,
  Code2,
  GitPullRequest,
  Loader2,
  Play,
  Search,
  ShieldCheck,
  Wrench,
  XCircle,
} from "lucide-react";

import {
  api,
  type Incident,
  type RepairCandidate,
} from "../api/client";

type StageStatus =
  | "idle"
  | "running"
  | "success"
  | "error";

type Stage = {
  key: string;
  number: string;
  title: string;
  description: string;
  status: StageStatus;
};

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function extractRepairCandidate(
  value: unknown,
): RepairCandidate | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const data = value as Record<string, unknown>;

  if (
    data.id &&
    typeof data.id === "string"
  ) {
    return data as unknown as RepairCandidate;
  }

  const candidates =
    data.repair_candidates;

  if (Array.isArray(candidates)) {
    const first = candidates[0];

    if (
      first &&
      typeof first === "object"
    ) {
      return first as RepairCandidate;
    }
  }

  return null;
}

function extractRca(value: unknown) {
  if (!value || typeof value !== "object") {
    return null;
  }

  const data =
    value as Record<string, unknown>;

  if (
    data.root_cause_analysis &&
    typeof data.root_cause_analysis === "object"
  ) {
    return data.root_cause_analysis;
  }

  return data;
}

function LifecycleStep({
  label,
  active,
  done,
}: {
  label: string
  active: boolean
  done: boolean
}) {
  return (
    <div
      className={`lifecycle-step ${
        active ? "active" : ""
      } ${done ? "done" : ""}`}
    >
      <span className="lifecycle-dot">
        {done ? "✓" : ""}
      </span>
      <span>{label}</span>
    </div>
  )
}

function LifecycleLine() {
  return <div className="lifecycle-line" />
}
export default function InvestigationPage({
  incident,
}: {
  incident?: Incident;
}) {
  const [stages, setStages] = useState<Stage[]>([
    {
      key: "detect",
      number: "01",
      title: "Detection",
      description: "Identify failure signals from incident logs.",
      status: "idle",
    },
    {
      key: "correlate",
      number: "02",
      title: "Correlation",
      description: "Connect related detections and failure patterns.",
      status: "idle",
    },
    {
      key: "rca",
      number: "03",
      title: "Root Cause",
      description: "Determine the most likely technical cause.",
      status: "idle",
    },
    {
      key: "localize",
      number: "04",
      title: "Code Localization",
      description: "Locate the affected source files and lines.",
      status: "idle",
    },
    {
      key: "repair",
      number: "05",
      title: "Repair",
      description: "Generate a controlled remediation candidate.",
      status: "idle",
    },
  ]);

  const [runningAll, setRunningAll] =
    useState(false);

  const [results, setResults] =
    useState<Record<string, unknown>>({});

  const [error, setError] =
    useState<string | null>(null);

  const [repairCandidate, setRepairCandidate] =
    useState<RepairCandidate | null>(null);

  const [repairAction, setRepairAction] =
    useState<StageStatus>("idle");

  const updateStage = (
    key: string,
    status: StageStatus,
  ) => {
    setStages((current) =>
      current.map((stage) =>
        stage.key === key
          ? { ...stage, status }
          : stage,
      ),
    );
  };

  const runStage = async (
    key: string,
  ) => {
    if (!incident?.id) {
      setError("No incident is available.");
      return null;
    }

    updateStage(key, "running");
    setError(null);

    try {
      let result: unknown;

      if (key === "detect") {
        result = await api.incidents.detect(
          incident.id,
        );
      }

      if (key === "correlate") {
        result = await api.incidents.correlate(
          incident.id,
        );
      }

      if (key === "rca") {
        result = await api.incidents.rca(
          incident.id,
        );
      }

      if (key === "localize") {
        result = await api.incidents.localize(
          incident.id,
        );
      }

      if (key === "repair") {
        result = await api.incidents.repair(
          incident.id,
        );

        const candidate =
          extractRepairCandidate(result);

        if (candidate) {
          setRepairCandidate(candidate);
        }
      }

      setResults((current) => ({
        ...current,
        [key]: result,
      }));

      updateStage(key, "success");

      return result;
    } catch (err) {
      updateStage(key, "error");

      const message =
        err instanceof Error
          ? err.message
          : "Investigation stage failed.";

      setError(message);

      throw err;
    }
  };

  const runFullInvestigation = async () => {
    if (!incident?.id) {
      setError("No incident is available.");
      return;
    }

    setRunningAll(true);
    setError(null);

    setResults({});
    setRepairCandidate(null);

    setStages((current) =>
      current.map((stage) => ({
        ...stage,
        status: "idle",
      })),
    );

    try {
      for (const stage of [
        "detect",
        "correlate",
        "rca",
        "localize",
        "repair",
      ]) {
        await runStage(stage);
      }
    } catch {
      // The individual stage already exposes
      // the real backend error to the UI.
    } finally {
      setRunningAll(false);
    }
  };

  const validateRepair = async () => {
    if (
      !incident?.id ||
      !repairCandidate?.id
    ) {
      return;
    }

    setRepairAction("running");
    setError(null);

    try {
      const result =
        await api.incidents.validateRepair(
          incident.id,
          repairCandidate.id,
        );

      setRepairCandidate(
        extractRepairCandidate(result) ||
          repairCandidate,
      );

      setResults((current) => ({
        ...current,
        validate: result,
      }));

      setRepairAction("success");
    } catch (err) {
      setRepairAction("error");

      setError(
        err instanceof Error
          ? err.message
          : "Repair validation failed.",
      );
    }
  };

  const verifyRepair = async () => {
    if (
      !incident?.id ||
      !repairCandidate?.id
    ) {
      return;
    }

    setRepairAction("running");
    setError(null);

    try {
      const result =
        await api.incidents.verifyRepair(
          incident.id,
          repairCandidate.id,
        );

      setRepairCandidate(
        extractRepairCandidate(result) ||
          repairCandidate,
      );

      setResults((current) => ({
        ...current,
        verify: result,
      }));

      setRepairAction("success");
    } catch (err) {
      setRepairAction("error");

      setError(
        err instanceof Error
          ? err.message
          : "Repair verification failed.",
      );
    }
  };

  const createPullRequest = async () => {
    if (
      !incident?.id ||
      !repairCandidate?.id
    ) {
      return;
    }

    setRepairAction("running");
    setError(null);

    try {
      const result =
        await api.incidents.createPullRequest(
          incident.id,
          repairCandidate.id,
        );

      const candidate =
        extractRepairCandidate(result);

      if (candidate) {
        setRepairCandidate(candidate);
      }

      setResults((current) => ({
        ...current,
        pull_request: result,
      }));

      setRepairAction("success");
    } catch (err) {
      setRepairAction("error");

      setError(
        err instanceof Error
          ? err.message
          : "GitHub pull request creation failed.",
      );
    }
  };

  const syncRepair = async () => {
    if (
      !incident?.id ||
      !repairCandidate?.id
    ) {
      return;
    }

    setRepairAction("running");
    setError(null);

    try {
      const result =
        await api.incidents.syncRepair(
          incident.id,
          repairCandidate.id,
        );

      const candidate =
        extractRepairCandidate(
          result,
        );

      if (candidate) {
        setRepairCandidate(candidate);
      }

      setResults((current) => ({
        ...current,
        sync: result,
      }));

      setRepairAction("success");
    } catch (err) {
      setRepairAction("error");

      setError(
        err instanceof Error
          ? err.message
          : "GitHub synchronization failed.",
      );
    }
  };

  const rca = extractRca(
    results.rca,
  ) as Record<string, unknown> | null;

  return (
    <div className="investigation-page">
      <div className="investigation-header">
        <div>
          <div className="investigation-kicker">
            AI INCIDENT INVESTIGATION
          </div>

          <h2>
            {incident?.title ||
              "No incident selected"}
          </h2>

          <p>
            {incident?.description ||
              "Select an incident to begin investigation."}
          </p>
        </div>

        <button
          className="run-investigation-button"
          onClick={runFullInvestigation}
          disabled={
            runningAll || !incident?.id
          }
        >
          {runningAll ? (
            <>
              <Loader2
                size={16}
                className="spin"
              />
              Investigating...
            </>
          ) : (
            <>
              <Play size={16} />
              Run Investigation
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="investigation-error">
          <XCircle size={17} />

          <div>
            <strong>Investigation stage failed</strong>
            <span>{error}</span>
          </div>
        </div>
      )}

      <div className="investigation-grid">
        <section className="investigation-panel pipeline-panel">
          <div className="investigation-panel-heading">
            <div>
              <h3>Investigation Pipeline</h3>
              <span>
                Real backend execution
              </span>
            </div>

            <span className="backend-live">
              API LIVE
            </span>
          </div>

          <div className="investigation-stages">
            {stages.map((stage) => (
              <div
                className={`investigation-stage stage-${stage.status}`}
                key={stage.key}
              >
                <div className="stage-number">
                  {stage.number}
                </div>

                <div className="stage-icon">
                  {stage.key === "detect" && (
                    <Activity size={17} />
                  )}

                  {stage.key === "correlate" && (
                    <Search size={17} />
                  )}

                  {stage.key === "rca" && (
                    <Brain size={17} />
                  )}

                  {stage.key === "localize" && (
                    <Code2 size={17} />
                  )}

                  {stage.key === "repair" && (
                    <Wrench size={17} />
                  )}
                </div>

                <div className="stage-copy">
                  <strong>{stage.title}</strong>
                  <span>{stage.description}</span>
                </div>

                <div className="stage-status">
                  {stage.status === "running" && (
                    <Loader2
                      size={15}
                      className="spin"
                    />
                  )}

                  {stage.status === "success" && (
                    <CheckCircle2 size={15} />
                  )}

                  {stage.status === "error" && (
                    <XCircle size={15} />
                  )}

                  {stage.status === "idle" && (
                    <span>READY</span>
                  )}
                </div>

                <button
                  className="stage-run"
                  disabled={
                    runningAll ||
                    stage.status === "running"
                  }
                  onClick={() =>
                    runStage(stage.key)
                  }
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            ))}
          </div>
        </section>

        <section className="investigation-panel incident-summary">
          <div className="investigation-panel-heading">
            <div>
              <h3>Incident Evidence</h3>
              <span>
                Production incident context
              </span>
            </div>
          </div>

          <div className="evidence-summary">
            <div className="evidence-severity">
              <AlertTriangle size={18} />

              <span>
                {incident?.severity?.toUpperCase() ||
                  "UNKNOWN"}
              </span>
            </div>

            <div className="evidence-row">
              <span>STATUS</span>
              <strong>
                {incident?.status || "—"}
              </strong>
            </div>

            <div className="evidence-row">
              <span>INCIDENT ID</span>
              <code>
                {incident?.id || "—"}
              </code>
            </div>

            <div className="evidence-row">
              <span>STARTED</span>
              <strong>
                {incident?.started_at
                  ? new Date(
                      incident.started_at,
                    ).toLocaleString()
                  : "—"}
              </strong>
            </div>
          </div>
        </section>
      </div>

      {rca && (
        <section className="investigation-panel rca-result">
          <div className="investigation-panel-heading">
            <div>
              <h3>Root Cause Analysis</h3>
              <span>
                Evidence-backed AI reasoning
              </span>
            </div>

            {typeof rca.confidence ===
              "number" && (
              <div className="confidence-badge">
                {Math.round(
                  rca.confidence * 100,
                )}
                % confidence
              </div>
            )}
          </div>

          <div className="rca-main">
            <div className="rca-cause">
              <span>LIKELY ROOT CAUSE</span>

              <h4>
                {String(
                  rca.root_cause ||
                    "Root cause identified by analysis",
                )}
              </h4>

              <p>
                {String(
                  rca.explanation ||
                    "No explanation returned.",
                )}
              </p>
            </div>

            <div className="rca-details">
              <div>
                <span>AFFECTED SERVICE</span>
                <strong>
                  {String(
                    rca.affected_service ||
                      "—",
                  )}
                </strong>
              </div>

              <div>
                <span>DEPENDENCY</span>
                <strong>
                  {String(
                    rca.dependency || "—",
                  )}
                </strong>
              </div>

              <div>
                <span>IMPACT</span>
                <strong>
                  {String(
                    rca.impact || "—",
                  )}
                </strong>
              </div>
            </div>
          </div>

          {Array.isArray(
            rca.evidence,
          ) && (
            <div className="rca-evidence">
              <span>EVIDENCE</span>

              {rca.evidence.map(
                (item, index) => (
                  <div
                    key={index}
                    className="evidence-chip"
                  >
                    <CheckCircle2 size={13} />
                    {String(item)}
                  </div>
                ),
              )}
            </div>
          )}
        </section>
      )}

      {repairCandidate && (
        <section className="investigation-panel repair-panel">
          <div className="investigation-panel-heading">
            <div>
              <h3>Repair Candidate</h3>
              <span>
                Controlled remediation lifecycle
              </span>
            </div>

            <span className="repair-status">
              {String(
                repairCandidate.status ||
                  "generated",
              ).toUpperCase()}
            </span>
          </div>

          <div className="repair-grid">
            <div>
              <span>FILE</span>
              <code>
                {repairCandidate.file_path ||
                  "—"}
              </code>
            </div>

            <div>
              <span>REPAIR TYPE</span>
              <strong>
                {repairCandidate.repair_type ||
                  "—"}
              </strong>
            </div>

            <div>
              <span>RISK</span>
              <strong>
                {repairCandidate.risk_level ||
                  "—"}
              </strong>
            </div>
          </div>

          <div className="repair-lifecycle">

  <LifecycleStep
    label="Generated"
    active={true}
    done={true}
  />

  <LifecycleLine />

  <LifecycleStep
    label="Validated"
    active={
      repairCandidate.status === "validated" ||
      repairCandidate.status === "verified" ||
      repairCandidate.status === "pull_request_created" ||
      repairCandidate.status === "applied"
    }
    done={
      repairCandidate.status === "validated" ||
      repairCandidate.status === "verified" ||
      repairCandidate.status === "pull_request_created" ||
      repairCandidate.status === "applied"
    }
  />

  <LifecycleLine />

  <LifecycleStep
    label="Verified"
    active={
      repairCandidate.status === "verified" ||
      repairCandidate.status === "pull_request_created" ||
      repairCandidate.status === "applied"
    }
    done={
      repairCandidate.status === "verified" ||
      repairCandidate.status === "pull_request_created" ||
      repairCandidate.status === "applied"
    }
  />

  <LifecycleLine />

  <LifecycleStep
    label="GitHub PR"
    active={Boolean(repairCandidate.github_pr_number)}
    done={Boolean(repairCandidate.github_pr_number)}
  />

  <LifecycleLine />

  <LifecycleStep
    label="Applied"
    active={repairCandidate.status === "applied"}
    done={repairCandidate.status === "applied"}
  />

</div>

<div className="repair-actions">

  <button
    onClick={validateRepair}
    disabled={
      repairAction === "running" ||
      !repairCandidate.id
    }
  >
    <ShieldCheck size={15} />
    Validate
  </button>

  <button
    onClick={verifyRepair}
    disabled={
      repairAction === "running" ||
      repairCandidate.status !== "validated"
    }
    title={
      repairCandidate.status !== "validated"
        ? "Candidate must be validated first"
        : "Verify repair"
    }
  >
    <CheckCircle2 size={15} />
    Verify
  </button>

  <button
    onClick={createPullRequest}
    disabled={
      repairAction === "running" ||
      repairCandidate.status !== "verified"
    }
    title={
      repairCandidate.status !== "verified"
        ? "Candidate must be verified first"
        : "Create GitHub pull request"
    }
  >
    <GitPullRequest size={15} />
    Create GitHub PR
  </button>

  <button
    onClick={syncRepair}
    disabled={
      repairAction === "running" ||
      !repairCandidate.github_pr_number
    }
    title={
      !repairCandidate.github_pr_number
        ? "Create a GitHub PR first"
        : "Synchronize GitHub merge state"
    }
  >
    <GitPullRequest size={15} />
    Sync Merge
  </button>

</div>

          {repairCandidate.github_pr_url && (
            <a
              className="github-pr-link"
              href={
                repairCandidate.github_pr_url
              }
              target="_blank"
              rel="noreferrer"
            >
              <GitPullRequest size={15} />
              View GitHub Pull Request
            </a>
          )}
        </section>
      )}

      <section className="investigation-panel raw-results">
        <div className="investigation-panel-heading">
          <div>
            <h3>Investigation Evidence Stream</h3>
            <span>
              Raw responses returned by the AegisAI API
            </span>
          </div>
        </div>

        {Object.keys(results).length === 0 ? (
          <div className="empty-investigation">
            <Activity size={20} />

            <strong>
              Investigation not started
            </strong>

            <span>
              Run the investigation to retrieve
              evidence from the backend.
            </span>
          </div>
        ) : (
          <div className="result-stream">
            {Object.entries(results).map(
              ([key, value]) => (
                <details
                  key={key}
                  className="result-block"
                  open={key === "rca"}
                >
                  <summary>
                    <span>
                      {key.toUpperCase()}
                    </span>

                    <ChevronRight size={14} />
                  </summary>

                  <pre>
                    {safeJson(value)}
                  </pre>
                </details>
              ),
            )}
          </div>
        )}
      </section>
    </div>
  );
}



