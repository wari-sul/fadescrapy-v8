import time
import asyncio
import psutil
import os
from collections import defaultdict
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from logging_setup import logger
from config import ADMIN_IDS

class AlertMonitor:
    """Monitors system metrics and sends alerts when thresholds are exceeded."""
    def __init__(self):
        self.last_alert = defaultdict(float)
        self.alert_thresholds = {
            'high_cpu': 80,    # CPU usage percentage
            'high_memory': 500, # Memory usage in MB
            'slow_response': 5  # Response time in seconds
        }
        self.cooldown = 3600  # Alert cooldown in seconds (1 hour)

    async def check_and_alert(self, bot: Bot):
        """Check system metrics and send alerts if needed."""
        try:
            current_time = time.time()
            process = psutil.Process(os.getpid())  # Use current process PID

            # Check CPU usage
            cpu_percent = process.cpu_percent()  # Gets process CPU since last call
            if cpu_percent > self.alert_thresholds['high_cpu']:
                if current_time - self.last_alert['cpu'] > self.cooldown:
                    await self._send_alert(
                        bot,
                        f"⚠️ High CPU Usage: {cpu_percent:.1f}%"
                    )
                    self.last_alert['cpu'] = current_time

            # Check memory usage
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)  # Resident Set Size in MB
            if memory_mb > self.alert_thresholds['high_memory']:
                if current_time - self.last_alert['memory'] > self.cooldown:
                    await self._send_alert(
                        bot,
                        f"⚠️ High Memory Usage: {memory_mb:.1f}MB"
                    )
                    self.last_alert['memory'] = current_time

        except psutil.NoSuchProcess:
            logger.warning("psutil.NoSuchProcess error during monitoring.")
        except Exception as e:
            logger.error(f"Error in alert monitoring: {e}", exc_info=True)

    async def _send_alert(self, bot: Bot, message: str):
        """Send alert to admin users."""
        logger.warning(f"Sending Alert: {message}")  # Log alerts
        for admin_id in ADMIN_IDS:
            if not admin_id:
                continue  # Skip empty IDs
            try:
                await bot.send_message(admin_id, message)
                await asyncio.sleep(0.1)  # Small delay to avoid hitting limits if many admins
            except TelegramAPIError as e:
                logger.error(f"Telegram API error sending alert to admin {admin_id}: {e}")
            except Exception as e:
                logger.error(f"Error sending alert to admin {admin_id}: {e}")

    def update_threshold(self, metric: str, value: int) -> bool:
        """Update monitoring threshold for a specific metric."""
        if metric in self.alert_thresholds:
            self.alert_thresholds[metric] = value
            logger.info(f"Updated {metric} threshold to {value}")
            return True
        return False

    def reset_cooldown(self, metric: str = None):
        """Reset cooldown for one or all metrics to allow immediate alerts."""
        if metric:
            if metric in self.last_alert:
                self.last_alert[metric] = 0
                return True
            return False
        else:
            # Reset all cooldowns
            self.last_alert = defaultdict(float)
            return True


# Create a singleton instance
alert_monitor = AlertMonitor()