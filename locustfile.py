import os
import uuid

import lorem
from locust import HttpUser, task, between

from aymurai.logging import get_logger

logger = get_logger(__name__)


class ServerStats:
    def __init__(self):
        self.n_cores: int = 0
        self.cpu_usage = 0

        self.memory_limit = 0
        self.memory_usage = 0

    @property
    def memory_percent(self):
        return self.memory_usage / self.memory_limit * 100 if self.memory_limit else 0

    def update_metrics(self, n_cores, cpu_percent, memory_limit, memory_percent):
        self.n_cores = n_cores
        self.cpu_usage = cpu_percent

        self.memory_limit = memory_limit
        self.memory_usage = memory_percent


stats = ServerStats()


def generate_text():
    paragraph = lorem.get_paragraph(
        count=1,
        comma=(0, 20),
        word_range=(4, 12),
        sentence_range=(0, 20),
        sep=os.linesep,
    )

    return f"{str(uuid.uuid4())} {paragraph}"


class DataPublic(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        self.fetch_server_stats()

    @task
    def predict_datapublic(self):

        payload = {"text": generate_text()}
        with self.client.post(
            "/datapublic/predict", json=payload, catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with status code: {response.status_code}")

        self.fetch_server_stats()

        print(
            "Request: predict (datapublic),"
            f" Response Time: {response.elapsed.total_seconds() * 1000}ms,"
            f" CPU Usage: {stats.cpu_usage}% ({stats.n_cores} cores),"  # noqa: E501
            f" Memory Usage: {stats.memory_usage} / {stats.memory_limit}MB ({stats.memory_percent}%)",  # noqa: E501
        )

    def fetch_server_stats(self):
        try:
            response = self.client.get("/server/stats/summary")

            if response.status_code != 200:
                logger.error("Error fetching server stats.")
                return

            data = response.json()

            ncores = data.get("cpu_core_limit", 0)
            cpu_usage = data.get("cpu_usage_percent", 0)

            mem_limit = data.get("memory_limit_mb", 0)
            mem_usage = data.get("memory_usage_mb", 0)

            stats.update_metrics(
                n_cores=ncores,
                cpu_percent=cpu_usage,
                memory_limit=mem_limit,
                memory_percent=mem_usage,
            )

        except Exception as e:
            print(f"Error fetching server stats: {e}")


class AnonymizerUser(HttpUser):
    wait_time = between(1, 2)

    def on_start(self):
        self.fetch_server_stats()

    @task
    def predict_anonimizer(self):

        payload = {"text": generate_text()}
        with self.client.post(
            "/anonymizer/predict", json=payload, catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with status code: {response.status_code}")

        self.fetch_server_stats()

        print(
            "Request: predict (anonymizer),"
            f" Response Time: {response.elapsed.total_seconds() * 1000}ms,"
            f" CPU Usage: {stats.cpu_usage}% ({stats.n_cores} cores),"  # noqa: E501
            f" Memory Usage: {stats.memory_usage} / {stats.memory_limit}MB ({stats.memory_percent}%)",  # noqa: E501
        )

    def fetch_server_stats(self):
        try:
            response = self.client.get("/server/stats/summary")

            if response.status_code != 200:
                logger.error("Error fetching server stats.")
                return

            data = response.json()

            ncores = data.get("cpu_core_limit", 0)
            cpu_usage = data.get("cpu_usage_percent", 0)

            mem_limit = data.get("memory_limit_mb", 0)
            mem_usage = data.get("memory_usage_mb", 0)

            stats.update_metrics(
                n_cores=ncores,
                cpu_percent=cpu_usage,
                memory_limit=mem_limit,
                memory_percent=mem_usage,
            )

        except Exception as e:
            print(f"Error fetching server stats: {e}")
