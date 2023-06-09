#!/bin/bash

output_format_awk="$(   
   cat <<'OUTPUTAWK'
BEGIN { v = "" }
v != $1 {
  print "# HELP hpmon_" $1 " HP metric "  $1;
  print "# TYPE hpmon_" $1 " gauge";;
  v = $1 
}
{print "hpmon_" $0} 
OUTPUTAWK
)"
format_status() {
if [[ "${value}" == *"OK"* ]];then
                value=1
            else
                value=0
            fi

}
format_errors() {
if [[ "${value}" == *"None"* ]];then
                value=0
            else
                value=1
            fi

}
format_output()   {
    sort | awk -F'{' "${output_format_awk}"
}
parse_ssacli_controller(){
    local controller=$1
    shift 
    local controller_mats=("$@")
    for matric in "${controller_mats[@]}"
    do
        key="$(echo $matric | awk -F: '{print $1}'| tr '[:upper:]' '[:lower:]'| tr -cd '[:alnum:]._'| sed 's/__/_/g')"
        value="$(echo $matric | awk -F: '{print $2}')"
        
        case "${key}" in
        *status*) format_status  ;;
        *temp*)  value=$value ;;
        *)  value="";;
	    esac
        if  [[ ! -z "$value" ]];then 
        echo "ssa_cli_controller_$key{controller=\"${controller}\"} ${value}" 
        fi
        
    done
}
parse_ssacli_device(){
    local controller=$1
    local device=$2
    shift 2
    local device_mats=("$@")
    for matric in "${device_mats[@]}"
    do
        key="$(echo $matric | awk -F: '{print $1}'| tr '[:upper:]' '[:lower:]'| tr -cd '[:alnum:]._')"
        value="$(echo $matric | awk -F: '{print $2}')"

	case "${key}" in
        status) format_status  ;;
        *temp*)  value=$value ;;
	*remain*) value=$(echo ${value} | awk '{print $1}'|sed 's/%//g');;
        *)  value="";;
        esac
        if  [[ ! -z "$value" ]];then
        echo "ssa_cli_device_$key{controller=\"${controller}\",device=\"${device}\"} ${value}"
        fi
    done
}

parse_ssacli_l_device(){
    local controller=$1
    local l_device=$2
    shift 2
    local l_device_mats=("$@")
    for matric in "${l_device_mats[@]}"
    do
        key="$(echo $matric | awk -F: '{print $1}'| tr '[:upper:]' '[:lower:]'| tr -cd '[:alnum:]._')"
        value="$(echo $matric | awk -F: '{print $2}')"

        case "${key}" in
        *status*) format_status  ;;
        *errors*) format_errors ;;
        *)  value="";;
            esac
        if  [[ ! -z "$value" ]];then
	        echo "ssa_cli_logical_device_$key{controller=\"${controller}\",logical_device=\"${l_device}\"} ${value}"
	fi
    done
}

controllers=$(ssacli ctrl all show detail | grep slot: -i| awk '{print $2}')
for controller in $controllers
do
  mapfile -t controller_matrics < <(/usr/sbin/ssacli ctrl slot=$controller show | grep ": "| sed 's/^[ ]*//g' | awk -F: '{gsub(/ /,"_",$1);print $1":"$2 }')
  parse_ssacli_controller "${controller}" "${controller_matrics[@]}"
  devices=$(ssacli ctrl slot=$controller pd all show | grep  physicaldrive | awk '{print $2}' )
  l_devices=$(ssacli ctrl slot=$controller ld all show | grep  logicaldrive | awk '{print $2}' )
  for device in ${devices}
  do
    mapfile -t device_matrics < <(/usr/sbin/ssacli ctrl slot=$controller pd "${device}" show | grep ": "| sed 's/^[ ]*//g' | awk -F: '{gsub(/ /,"_",$1);print $1":"$2 }')
    parse_ssacli_device "${controller}" "${device}" "${device_matrics[@]}"       
  done
  for l_device in ${l_devices}
  do
    mapfile -t l_device_matrics < <(/usr/sbin/ssacli ctrl slot=$controller ld "${l_device}" show | grep ": "| sed 's/^[ ]*//g' | awk -F: '{gsub(/ /,"_",$1);print $1":"$2 }')
    parse_ssacli_l_device "${controller}" "${l_device}" "${l_device_matrics[@]}"       
  done
done | format_output
