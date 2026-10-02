#!/bin/bash
set -euo pipefail
exec /opt/spark/sbin/start-connect-server.sh \
 --master 'local[2]' \
 --conf spark.driver.memory=2g \
 --conf spark.sql.shuffle.partitions=2 \
 --conf spark.sql.session.timeZone=UTC \
 --conf spark.ui.enabled=false \
 --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
 --jars /lab/jars/iceberg-spark-runtime-4.1_2.13-1.11.0.jar,/lab/jars/iceberg-aws-bundle-1.11.0.jar
