
# ps_siq_stats
This script is designed to query multiple PowerScale clusters for SyncIQ replication statistics. It reports on the latest successful replication for every SyncIQ policy on each cluster. This information can be used in a dashboard to display the recovery point for any given replication policy. The script utilizes the OneFS Platform API (PAPI) to retrieve the data and a user and password with the proper permissions is required for proper function.

This script currently only supports providing data to a Prometheus database.

## Installation

### Dependencies
The following Python libraries are required for this script to run:
 - yaml
 - prometheus-client

### Configuration
The script requires a YAML file with user, password, and endpoint settings. The configuration file can contain multiple clusters to monitor and each cluster has its own settings. The YAML file should have the following format:

    ---
    - cluster:
        user: "<user_name>"
        password: "<password>"
        endpoint: "<endpoint>"
    - cluster:
        user: "siq_poll_user"
        password: "a_secret"
        endpoint: "192.168.200.50:8080"

An example configuration can be found in the file: **example_config.yml**

The script listens on port 8000 by default. This can be changed with a CLI option (--port) or by setting the environment variable PS_SIQ_STATS_PORT to the desired value.

Help and other options for the script can be found by running the script with the *--help* option.

## Execution

### Create RBAC user and role on clusters
If you need to create an RBAC user or role on the clusters for the script to use the following example commands can be used.

    isi auth users create ps_siq_stats --enabled=true --set-password
    isi auth roles create --name=siq_stats_poll --zone=system
    isi auth roles modify siq_stats_poll --add-priv-read=ISI_PRIV_LOGIN_PAPI --add-priv-read=ISI_PRIV_SYNCIQ --add-user=ps_siq_stats

Create a YAML configuration file that contains the user, password, and endpoint information for each of the clusters you wish to monitor. The file **example_config.yml** can be used as an example template.

### Run the script
    (nohup python3 ps_siq_stats.py --config=config.yml &)

As an alternative, a PYZ release of the code is also available which bundles all the script files required. This method may be more portable and easier to use.

    (nohup python3 ps_siq_stats.pyz --config=config.yml &)

### Verifying operation
After starting the script, a web browser can be used to validate that the script is performing properly. Navigate to the IP address or use localhost and the port number to get a page with the collected statistics. An example output follows.

    # HELP isilon_siq_recovery_point_bytes Bytes transferred in the last successful SyncIQ run
    # TYPE isilon_siq_recovery_point_bytes gauge
    isilon_siq_recovery_point_bytes{cluster_name="ps_cluster",policy="s1",source_path="/ifs/synctest/src1",target_cluster="127.0.0.1",target_path="/ifs/synctest/tgt1"} 1312.0
    # HELP isilon_siq_recovery_point_job_id SyncIQ job ID for this replication
    # TYPE isilon_siq_recovery_point_job_id gauge
    isilon_siq_recovery_point_job_id{cluster_name="ps_cluster",policy="s1",source_path="/ifs/synctest/src1",target_cluster="127.0.0.1",target_path="/ifs/synctest/tgt1"} 2616.0
    # HELP isilon_siq_recovery_point_sync_duration_seconds Time in seconds the SynciQ policy took to run to completion
    # TYPE isilon_siq_recovery_point_sync_duration_seconds gauge
    isilon_siq_recovery_point_sync_duration_seconds{cluster_name="ps_cluster",policy="s1",source_path="/ifs/synctest/src1",target_cluster="127.0.0.1",target_path="/ifs/synctest/tgt1"} 7.0
    # HELP isilon_siq_recovery_point_timestamp_milliseconds Recovery point for the SyncIQ policy
    # TYPE isilon_siq_recovery_point_timestamp_milliseconds gauge
    isilon_siq_recovery_point_timestamp_milliseconds{cluster_name="ps_cluster",policy="s1",source_path="/ifs/synctest/src1",target_cluster="127.0.0.1",target_path="/ifs/synctest/tgt1"} 1.717746601e+012
    # HELP isilon_siq_recovery_point_bytes Bytes transferred in the last successful SyncIQ run
    # TYPE isilon_siq_recovery_point_bytes gauge
    isilon_siq_recovery_point_bytes{cluster_name="ps_cluster",policy="s2",source_path="/ifs/synctest/src2",target_cluster="127.0.0.1",target_path="/ifs/synctest/tgt2"} 1312.0
    # HELP isilon_siq_recovery_point_job_id SyncIQ job ID for this replication
    # TYPE isilon_siq_recovery_point_job_id gauge
    isilon_siq_recovery_point_job_id{cluster_name="ps_cluster",policy="s2",source_path="/ifs/synctest/src2",target_cluster="127.0.0.1",target_path="/ifs/synctest/tgt2"} 411.0
    # HELP isilon_siq_recovery_point_sync_duration_seconds Time in seconds the SynciQ policy took to run to completion
    # TYPE isilon_siq_recovery_point_sync_duration_seconds gauge
    isilon_siq_recovery_point_sync_duration_seconds{cluster_name="ps_cluster",policy="s2",source_path="/ifs/synctest/src2",target_cluster="127.0.0.1",target_path="/ifs/synctest/tgt2"} 8.0
    # HELP isilon_siq_recovery_point_timestamp_milliseconds Recovery point for the SyncIQ policy
    # TYPE isilon_siq_recovery_point_timestamp_milliseconds gauge
    isilon_siq_recovery_point_timestamp_milliseconds{cluster_name="ps_cluster",policy="s2",source_path="/ifs/synctest/src2",target_cluster="127.0.0.1",target_path="/ifs/synctest/tgt2"} 1.717598124e+012

### Performance
The default polling interval for Prometheus is 15 seconds. For the SyncIQ statistics, these metrics change only when SyncIQ jobs complete. These are usually on the order of once a day or several times per day. Thus a larger polling interval is suggested. Use as long an interval as possible to reduce the load of re-calculating all the SyncIQ statistics. The interval may also need to be increased if a lot of clusters are monitored. An interval of 5 minutes may be a reasonable compromise between low overhead and having current information. 

## Data format
The script sends 3 gauge metrics for each SyncIQ policy to Prometheus. Each attribute includes labels for the following SyncIQ fields:

 - Cluster name (cluster_name)
 - SyncIQ policy name (policy)
 - SyncIQ source path (source_path)
 - SyncIQ target cluster (target_cluster)
 - SyncIQ target path (target_path)

The 3 metrics with values are:
 - isilon_siq_recovery_point_job_id (This is the actual job ID on the source cluster for the most recent completed replication job)
 - isilon_siq_recovery_point_sync_duration_seconds (Runtime in seconds for the last successful replication job)
 - isilon_siq_recovery_point_timestamp_milliseconds (Epoch time in milliseconds that represents the time when the last successful SyncIQ job started. This represents the recovery point for this policy)

## Security
The script connects to a PowerScale cluster over PAPI. This requires a user name and a password for the creation of a PAPI session. These password are kept in a YAML configuration file. This file should have permission set so that only the script runner can read the file.

The user connecting to the cluster needs only the following RBAC privileges:
Read - ISI_PRIV_LOGIN_PAPI (Required to access PAPI)
Read - ISI_PRIV_SYNCIQ (Required to access SyncIQ settings)

## Issues, bug reports, and suggestions
For any issues with the script, please re-run the script with debug enabled (--debug command line option) and open an issue with the debug output and description of the problem.
