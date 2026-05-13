"""Kafka topic administration — idempotent topic creation with graceful degradation."""

from __future__ import annotations

import time
from typing import Dict, List

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

REQUIRED_TOPICS: List[Dict[str, int]] = [
    {"name": "transactions.raw", "num_partitions": 3, "replication_factor": 1},
    {"name": "transactions.scored", "num_partitions": 3, "replication_factor": 1},
    {"name": "alerts.generated", "num_partitions": 1, "replication_factor": 1},
]


def ensure_kafka_topics() -> bool:
    """Create required Kafka topics if they do not already exist.

    Returns ``True`` when every topic is confirmed ready, ``False`` on
    partial or total failure.  Never raises — all errors are logged.
    """
    try:
        from confluent_kafka.admin import AdminClient, NewTopic
        from confluent_kafka import KafkaException
    except ImportError:
        logger.error("confluent_kafka_missing",
                     extra={"detail": "confluent-kafka package is not installed"})
        return False

    try:
        admin = AdminClient({"bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS})
    except KafkaException as exc:
        logger.error("kafka_admin_connect_failed",
                      extra={"error": str(exc),
                             "bootstrap": settings.KAFKA_BOOTSTRAP_SERVERS})
        return False

    # Discover existing topics
    try:
        cluster_meta = admin.list_topics(timeout=10)
        existing_topics: set[str] = set(cluster_meta.topics.keys())
    except KafkaException as exc:
        logger.error("kafka_list_topics_failed", extra={"error": str(exc)})
        return False

    topics_to_create: list[NewTopic] = []
    for spec in REQUIRED_TOPICS:
        if spec["name"] not in existing_topics:
            topics_to_create.append(
                NewTopic(
                    topic=spec["name"],
                    num_partitions=spec["num_partitions"],
                    replication_factor=spec["replication_factor"],
                )
            )

    if not topics_to_create:
        logger.info("kafka_topics_already_exist",
                     extra={"topics": [s["name"] for s in REQUIRED_TOPICS]})
        return True

    # Request creation and poll futures
    futures = admin.create_topics(topics_to_create)

    all_ok = True
    for topic_name, future in futures.items():
        try:
            future.result(timeout=10)
            logger.info("kafka_topic_created", extra={"topic": topic_name})
        except KafkaException as exc:
            # Topic may have been concurrently created — treat TOPIC_ALREADY_EXISTS as success
            err_str = str(exc)
            if "TOPIC_ALREADY_EXISTS" in err_str:
                logger.info("kafka_topic_already_exists", extra={"topic": topic_name})
            else:
                logger.error("kafka_topic_create_failed",
                              extra={"topic": topic_name, "error": err_str})
                all_ok = False
        except Exception as exc:
            logger.error("kafka_topic_create_unexpected",
                          extra={"topic": topic_name, "error": str(exc)})
            all_ok = False

    # Final verification — wait briefly and confirm all topics visible
    time.sleep(1)
    try:
        refreshed = admin.list_topics(timeout=10)
        refreshed_names = set(refreshed.topics.keys())
        for spec in REQUIRED_TOPICS:
            if spec["name"] not in refreshed_names:
                logger.warning("kafka_topic_not_visible_after_create",
                                extra={"topic": spec["name"]})
                all_ok = False
    except KafkaException as exc:
        logger.warning("kafka_verify_topics_failed", extra={"error": str(exc)})
        all_ok = False

    return all_ok
