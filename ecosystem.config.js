module.exports = {
  apps: [
    {
      name: "trading-bot",
      script: "./run_bot.sh",
      interpreter: "bash",
      cwd: "/root/trading-assistant-bot",
      autorestart: true,
      watch: false,
      max_memory_restart: "500M",
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
  ],
};
