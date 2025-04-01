import time
import os
import psutil
from collections import defaultdict
from datetime import timedelta
from logging_setup import logger

class BotMetrics:
    """Tracks and records bot performance metrics."""
    def __init__(self):
        self.command_latency = defaultdict(list)  # Command -> List of execution times
        self.error_counts = defaultdict(int)      # Command -> Error count
        self.user_activity = defaultdict(int)     # User ID -> Command count
        self.start_time = time.time()
        self.max_latency_entries = 1000  # Max entries per command to keep
        self.activity_cleanup_interval = 86400  # 24 hours
        self.last_activity_cleanup = time.time()

    def log_command(self, command: str, user_id: int, execution_time: float, success: bool = True):
        """Log command execution metrics."""
        command_key = command[1:] if command.startswith('/') else command

        self.command_latency[command_key].append(execution_time)
        # Keep only last N latency measurements per command
        if len(self.command_latency[command_key]) > self.max_latency_entries:
            self.command_latency[command_key] = self.command_latency[command_key][-self.max_latency_entries:]

        self.user_activity[user_id] += 1
        if not success:
            self.error_counts[command_key] += 1

    def get_stats(self) -> dict:
        """Get current bot statistics."""
        uptime_seconds = time.time() - self.start_time
        total_commands_processed = sum(len(latencies) for latencies in self.command_latency.values())
        total_errors = sum(self.error_counts.values())

        try:
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / (1024 * 1024)  # MB
        except psutil.NoSuchProcess:
            memory_mb = 0
            logger.warning("psutil.NoSuchProcess error getting memory usage.")

        stats = {
            "uptime": str(timedelta(seconds=int(uptime_seconds))),
            "total_active_users_tracked": len(self.user_activity),  # Users active since last cleanup
            "total_commands_logged": total_commands_processed,
            "total_errors_logged": total_errors,
            "overall_error_rate": (total_errors / total_commands_processed * 100) if total_commands_processed else 0,
            "memory_usage_mb": memory_mb,
            "command_stats": {}
        }

        for cmd, times in self.command_latency.items():
            if times:
                usage_count = len(times)
                cmd_errors = self.error_counts[cmd]
                stats["command_stats"][cmd] = {
                    "avg_latency_ms": (sum(times) / usage_count) * 1000,
                    "max_latency_ms": max(times) * 1000,
                    "min_latency_ms": min(times) * 1000,
                    "usage_count": usage_count,
                    "error_count": cmd_errors,
                    "error_rate_percent": (cmd_errors / usage_count * 100) if usage_count else 0,
                }
        # Sort command stats by usage count
        stats["command_stats"] = dict(sorted(
            stats["command_stats"].items(), 
            key=lambda item: item[1]['usage_count'], 
            reverse=True
        ))

        return stats

    def cleanup_old_data(self):
        """Remove old metrics data to prevent memory bloat."""
        current_time = time.time()

        # Clean up user activity if interval passed
        if current_time - self.last_activity_cleanup > self.activity_cleanup_interval:
            # Reset activity counts for the next period
            self.user_activity = defaultdict(int)
            self.last_activity_cleanup = current_time
            logger.info("Cleaned up user activity metrics.")


# Create singleton instance
metrics = BotMetrics()