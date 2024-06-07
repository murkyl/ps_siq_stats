#!/usr/bin/env python
# -*- coding: utf8 -*-
"""
Prometheus client to export PowerScale SyncIQ replication policy status
"""
# fmt: off
__title__         = "ps_siq_stats"
__version__       = "0.1.0"
__date__          = "07 June 2024"
__license__       = "MIT"
__author__        = "Andrew Chung <andrew.chung@dell.com>"
__maintainer__    = "Andrew Chung <andrew.chung@dell.com>"
__email__         = "andrew.chung@dell.com"
# fmt: on
import datetime
import inspect
import logging
import os
import signal
import sys
import time

import helpers.constants as constants
import helpers.options_parser as options_parser
import libs.papi_lite as papi_lite

try:
    import yaml
except:
    sys.stderr.write(constants.STR_MISSING_MODULE_YAML)
    sys.exit(2)
try:
    import prometheus_client as prometheus_client
    import prometheus_client.core as prometheus_core

    PROMETHEUS_MODULES_AVAILABLE = True
except:
    PROMETHEUS_MODULES_AVAILABLE = False

DEFAULT_LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s"
LOG = logging.getLogger()
PSCALE_ENDPOINTS = []
PSCALE_CONNECTIONS = []
SEC_TO_MILLISEC = 1000
URI_CLUSTER_CONFIG = "/cluster/config"
URI_SIQ_POLICIES = "/sync/policies"
URI_SIQ_REPORTS = "/sync/reports"


def get_cluster_name(papi):
    data = papi.rest_call(
        URI_CLUSTER_CONFIG,
        "GET",
    )
    if data[0] != 200:
        raise Exception("Error in PAPI request to {url}:\n{err}".format(err=str(data), url=URI_CLUSTER_CONFIG))
    cluster_name = data[2]["name"]
    return cluster_name


def get_siq_policies(papi):
    data = papi.rest_call(
        URI_SIQ_POLICIES,
        "GET",
    )
    if data[0] != 200:
        raise Exception("Error in PAPI request to {url}:\n{err}".format(err=str(data), url=URI_SIQ_POLICIES))
    return data[2].get("policies")


def get_siq_report(papi, policy_name, state=None, limit=10):
    if not state:
        state = "finished"
    data = papi.rest_call(
        URI_SIQ_REPORTS,
        "GET",
        query_args={
            "limit": "%s" % limit,
            "policy_name": policy_name,
            "reports_per_policy": "%s" % limit,
            "state": state,
        },
    )
    if data[0] != 200:
        raise Exception("Error in PAPI request to {url}:\n{err}".format(URI_SIQ_REPORTS))
    return data[2].get("reports")


def get_siq_rp_stats(papi_endpoint):
    siq_policies = {}
    siq_reports = {}
    cluster_name = ""
    results = []

    cluster_name = get_cluster_name(papi_endpoint)
    cluster_siq_policies = get_siq_policies(papi_endpoint)
    for item in cluster_siq_policies:
        siq_policies[item["name"]] = item
    for policy_name in siq_policies.keys():
        all_reports = get_siq_report(papi_endpoint, policy_name, limit=1)
        finished_reports = sorted(
            [x for x in all_reports if x["state"] == "finished" and x["end_time"]],
            key=lambda x: x["end_time"],
        )
        siq_reports[policy_name] = finished_reports[-1]
    for policy_name in siq_policies.keys():
        policy = siq_policies[policy_name]
        report = siq_reports[policy_name]
        results.append({"cluster_name": cluster_name, "policy": policy, "report": report})
    return results


def print_stats(siq_stats, footer=True):
    for result in siq_stats:
        cluster_name = result["cluster_name"]
        policy = result["policy"]
        report = result["report"]
        print("Source cluster: %s" % cluster_name)
        print("Policy name   : %s" % policy["name"])
        print("Source path   : %s" % policy["source_root_path"])
        print("Target cluster: %s" % policy["target_host"])
        print("Target path   : %s" % policy["target_path"])
        time_str = datetime.datetime.fromtimestamp(report["start_time"]).strftime("%Y-%m-%d %H:%M:%S")
        print("Recovery point: %s" % time_str)
        print("Sync duration : %s seconds" % (report["end_time"] - report["start_time"]))
        print("Last successful job: %s" % report["job_id"])
        print("Bytes transferred  : %s" % report["bytes_transferred"])
        if footer:
            print("")


def setup_logging(options):
    log_handler = logging.StreamHandler()
    log_handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))
    LOG.addHandler(log_handler)
    if options.get("debug", 0):
        LOG.setLevel(logging.DEBUG)
    else:
        LOG.setLevel(logging.INFO)
    if options.get("debug", 0) < 2:
        # Disable loggers for sub modules
        for mod_name in ["libs.papi_lite"]:
            module_logger = logging.getLogger(mod_name)
            module_logger.setLevel(logging.WARN)


def signal_handler(signum, frame):
    global PSCALE_CONNECTIONS
    if signum in [signal.SIGINT, signal.SIGTERM]:
        sys.stdout.write("Terminating SyncIQ stats proxy\n")
        sys.exit(0)


def to_float(val):
    if not val:
        return 0
    return float(val)


class SIQCollector(object):
    global PSCALE_CONNECTIONS

    def __init__(self):
        self.base_name = "isilon"
        self.stat_name = "siq_recovery_point"
        self.labels = [
            "cluster_name",
            "policy",
            "source_path",
            "target_cluster",
            "target_path",
        ]

    def collect(self):
        for conn in PSCALE_CONNECTIONS:
            siq_stats = get_siq_rp_stats(conn)
            # print_stats(siq_stats)
            for result in siq_stats:
                policy = result["policy"]
                report = result["report"]
                for stat in [
                    ["bytes", "Bytes transferred in the last successful SyncIQ run"],
                    ["job_id", "SyncIQ job ID for this replication"],
                    [
                        "sync_duration_seconds",
                        "Time in seconds the SynciQ policy took to run to completion",
                    ],
                    ["timestamp_milliseconds", "Recovery point for the SyncIQ policy"],
                ]:
                    key_name = "_".join([self.base_name, self.stat_name, stat[0]])
                    description = stat[1]
                    label_values = [
                        result["cluster_name"],
                        policy["name"],
                        policy["source_root_path"],
                        policy["target_host"],
                        policy["target_path"],
                    ]
                    metric = prometheus_core.GaugeMetricFamily(key_name, description, labels=self.labels)
                    if stat[0] == "bytes":
                        metric.add_metric(label_values, to_float(report["bytes_transferred"]))
                    elif stat[0] == "job_id":
                        metric.add_metric(label_values, to_float(report["job_id"]))
                    elif stat[0] == "sync_duration_seconds":
                        metric.add_metric(
                            label_values,
                            to_float(report["end_time"] - report["start_time"]),
                        )
                    elif stat[0] == "timestamp_milliseconds":
                        metric.add_metric(
                            label_values,
                            to_float(report["start_time"]) * SEC_TO_MILLISEC,
                        )
                    else:
                        # Ignore any unknown values
                        continue
                    yield metric


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Setup command line parser and parse agruments
    (parser, options, args) = options_parser.parse(sys.argv, __version__, __date__)
    setup_logging(options)
    # Validate config options
    # If there are argument errors, exit with 1
    if not options["config"]:
        sys.stdout.write("A YAML configuration file is a required parameter\n")
        sys.exit(1)
    try:
        with open(options["config"], "r") as cfg_file:
            cfg_data = yaml.safe_load(cfg_file)
    except Exception as e:
        sys.stdout.write("An error occurred loading the configuration file: %s\n" % e)
        sys.exit(3)
    if not cfg_data:
        sys.stdout.write("An error occurred loading the configuration file: %s\n" % e)
        sys.exit(3)
    try:
        for item in cfg_data:
            if "cluster" in item:
                for key in ["endpoint", "password", "user"]:
                    if key not in item["cluster"]:
                        LOG.error("Missing key (%s) in YAML configuration. Partial entry: %s" % (key, item["cluster"]))
                        break
                else:
                    PSCALE_ENDPOINTS.append(item["cluster"])
    except Exception as e:
        sys.stdout.write("An error occurred parsing the configuration file: %s\n" % e)
        sys.exit(4)

    if not PSCALE_CONNECTIONS:
        for endpoint in PSCALE_ENDPOINTS:
            PSCALE_CONNECTIONS.append(
                papi_lite.papi_lite(
                    user=endpoint["user"],
                    password=endpoint["password"],
                    server=endpoint["endpoint"],
                )
            )
            LOG.debug("Connected to: %s" % endpoint["endpoint"])
            # Set sensitive information to None
            endpoint["password"] = None

    if not PROMETHEUS_MODULES_AVAILABLE:
        sys.stderr.write(constants.STR_MISSING_MODULE_PROMETHEUS)
        sys.exit(2)
    try:
        prometheus_core.REGISTRY.unregister(prometheus_client.GC_COLLECTOR)
        prometheus_core.REGISTRY.unregister(prometheus_client.PLATFORM_COLLECTOR)
        prometheus_core.REGISTRY.unregister(prometheus_client.PROCESS_COLLECTOR)
    except Exception as e:
        LOG.error("Unable to unregister default Prometheus metrics: %s" % e)
    prometheus_core.REGISTRY.register(SIQCollector())
    # Start up the server to expose the metrics.
    prometheus_client.start_http_server(options["port"])
    while True:
        time.sleep(60)


if __name__ == "__main__" or __file__ == None:
    main()
