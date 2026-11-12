# Contributing

The Prometheus Community welcomes contributions to the node_exporter textfile
collector script repository adhering to the following criteria:

Ideally, scripts should not duplicate functionality that is already available in
dedicated exporters. The textfile collector script collection is largely
intended to provide stop-gap measures, parsing output from third-party tools
(e.g. RAID controller utilities), or in situations where elevated privileges
(e.g. root access) are required.

Textfile collector scripts should be written in either Python or shell script.
Scripts are expected to output metrics to `stdout` in the [Prometheus text-based
format][1], and should not directly write to an output file.

Metric and label names should follow the Prometheus [naming guidelines][2].

## Python Scripts

- Must use Python 3.x.
- Must use the official Prometheus Python [client library][3], which greatly
  simplifies ensuring valid metric output format.
- Must pass a [flake8][4] lint check (enforced by CI pipeline).

## Shell Scripts

- Must use either Bash or generic POSIX-compatible shell (e.g. `/bin/sh`).
- Must pass a [shellcheck][5] lint check (enforced by CI pipeline).
- With the exception of specific third-party / closed-source tools, should avoid
  using "exotic" commands that are unlikely to be present on typical systems.

[1]: https://prometheus.io/docs/instrumenting/exposition_formats/#text-based-format
[2]: https://prometheus.io/docs/practices/naming/
[3]: https://github.com/prometheus/client_python
[4]: https://flake8.pycqa.org/
[5]: https://www.shellcheck.net/
