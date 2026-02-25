const BASE_ENV = {
  VAULT_PATH: process.env.VAULT_PATH || `${process.env.HOME}/AI_Employee_Vault`,
  DEV_MODE: "false",
  DRY_RUN: "false",
};

const BASE_ENV_DEV = {
  DEV_MODE: "true",
  DRY_RUN: "true",
};

const RESTART_POLICY = {
  autorestart: true,
  max_restarts: 10,
  restart_delay: 5000,
  kill_timeout: 10000,
  listen_timeout: 10000,
};

const LOG_OPTS = {
  log_date_format: "YYYY-MM-DD HH:mm:ss Z",
  merge_logs: true,
};

module.exports = {
  apps: [
    {
      name: "ai-employee-orchestrator",
      script: "uv",
      args: "run python src/orchestrator/orchestrator.py",
      cwd: __dirname,
      env: BASE_ENV,
      env_development: BASE_ENV_DEV,
      ...RESTART_POLICY,
      ...LOG_OPTS,
      error_file: "./logs/orchestrator-error.log",
      out_file: "./logs/orchestrator-out.log",
    },
    {
      name: "ai-employee-filesystem-watcher",
      script: "uv",
      args: "run python -m src.watchers.filesystem_watcher",
      cwd: __dirname,
      env: BASE_ENV,
      env_development: BASE_ENV_DEV,
      ...RESTART_POLICY,
      ...LOG_OPTS,
      error_file: "./logs/filesystem-watcher-error.log",
      out_file: "./logs/filesystem-watcher-out.log",
    },
    {
      name: "ai-employee-gmail-watcher",
      script: "uv",
      args: "run python -m src.watchers.gmail_watcher",
      cwd: __dirname,
      env: BASE_ENV,
      env_development: BASE_ENV_DEV,
      ...RESTART_POLICY,
      ...LOG_OPTS,
      error_file: "./logs/gmail-watcher-error.log",
      out_file: "./logs/gmail-watcher-out.log",
    },
    {
      name: "ai-employee-whatsapp-watcher",
      script: "uv",
      args: "run python -m src.watchers.whatsapp_watcher",
      cwd: __dirname,
      env: { ...BASE_ENV, DISPLAY: ":0" },
      env_development: BASE_ENV_DEV,
      ...RESTART_POLICY,
      ...LOG_OPTS,
      error_file: "./logs/whatsapp-watcher-error.log",
      out_file: "./logs/whatsapp-watcher-out.log",
    },
    {
      name: "ai-employee-web-dashboard",
      script: "uv",
      args: "run python src/cli/web_dashboard.py",
      cwd: __dirname,
      env: {
        ...BASE_ENV,
        PORT: process.env.DASHBOARD_PORT || "8080",
        DISPLAY: ":0",
      },
      env_development: BASE_ENV_DEV,
      ...RESTART_POLICY,
      ...LOG_OPTS,
      error_file: "./logs/web-dashboard-error.log",
      out_file: "./logs/web-dashboard-out.log",
    },
    // ── Platinum: Cloud Agent (run this app only on the GCP VM) ──────────────
    {
      name: "ai-employee-cloud-agent",
      script: "uv",
      args: "run python src/cloud/agent/cloud_agent.py",
      cwd: __dirname,
      // AGENT_NAME distinguishes cloud from local in claim-by-move rule
      env: { ...BASE_ENV, AGENT_NAME: "cloud", DRY_RUN: "true" },
      env_development: { ...BASE_ENV_DEV, AGENT_NAME: "cloud" },
      ...RESTART_POLICY,
      ...LOG_OPTS,
      error_file: "./logs/cloud-agent-error.log",
      out_file: "./logs/cloud-agent-out.log",
    },
    // ── Platinum: Vault Sync (cron-driven, managed separately) ───────────────
    // vault_sync.sh is run via cron every 2 minutes — not via PM2.
    // To set up: crontab -e → add:
    //   */2 * * * * /path/to/repo/src/cloud/sync/vault_sync.sh >> /tmp/vault-sync.log 2>&1
  ],
};
