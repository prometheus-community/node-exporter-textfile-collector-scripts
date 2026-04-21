#!/usr/bin/awk -nf

#
# Converts output of `ipmitool chassis status` to prometheus format.
#
# With GNU awk:
#   ipmitool chassis status | ./ipmitool_chassis.sh > ipmitool_chassis.prom
#
# With BSD awk:
#   ipmitool chassis status | awk -f ./ipmitool_chassis.sh > ipmitool_chassis.prom
#

function export(values, name) {
	if (values["metric_count"] < 1) {
		return
	}
	delete values["metric_count"]

	printf("# HELP %s%s %s sensor reading from ipmitool\n", namespace, name, help[name]);
	printf("# TYPE %s%s gauge\n", namespace, name);
	for (sensor in values) {
		printf("%s%s{sensor=\"%s\"} %f\n", namespace, name, sensor, values[sensor]);
	}
}

# Fields are colon separated, with space padding.
BEGIN {
	FS = "[ ]*[:][ ]*";
	namespace = "node_ipmi_chassis_";

	# Friendly description of the type of sensor for HELP.
	help["fault"] = "Chassis Fault";

	fault["metric_count"] = 0;
}

# Not a valid line.
{
	if (NF < 2) {
		next
	}
}

# $2 is value field.
$2 ~ /na/ {
	next
}

# $1 is type field.
$1 ~ /Fault/ {
	if ($2 == "true") {
		fault[$1] = 1
	} else {
		fault[$1] = 0
	}
	fault["metric_count"]++;
}

END {
	export(fault, "fault");
}
