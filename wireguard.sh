#!/bin/sh

# Loads data for wireguard interfaces

DATA=$(wg show all dump)

RAW_INTERFACES=$(echo "$DATA" | awk -F ' ' '{print $1}')

SAVEIFS=$IFS   # Save current IFS (Internal Field Separator)
IFS=$'\n'      # Change IFS to newline char
INTERFACES=($RAW_INTERFACES) # split the `names` string into an array by the same name
IFS=$SAVEIFS   # Restore original IFS
INTERFACES=($(echo "${INTERFACES[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' '))

declare -A ENDPOINTS
declare -A ALLOWEDIPS
declare -A LATESTHANDSHAKE
declare -A TRANSFERRX
declare -A TRANSFERTX
declare -A PERSISTENTKEEPALIVE

for interface in "${INTERFACES[@]}"; do
    RAW_IF_LINES=$(echo "$DATA" | grep $interface)
    IF_LINES=${RAW_IF_LINES%$'\n'*}


    SAVEIFS=$IFS   # Save current IFS (Internal Field Separator)
    IFS=$'\n'      # Change IFS to newline char
    IF_LINES=($RAW_IF_LINES) # split the `names` string into an array by the same name
    IFS=$SAVEIFS   # Restore original IFS


    # Parse all the Peers
    for peer in "${IF_LINES[@]:1}"; do

        SAVEIFS=$IFS   # Save current IFS (Internal Field Separator)
        IFS=$' '      # Change IFS to newline char
        PARTS=($peer) # split the `names` string into an array by the same name
        IFS=$SAVEIFS   # Restore original IFS

        if ! [ ${ENDPOINTS[$interface]+_} ]; then
            ENDPOINTS[$interface]=${PARTS[3]}
        else
            PREVIOUS=${ENDPOINTS[$interface]}
            PREVIOUS+=','
            PREVIOUS+=${PARTS[3]}
            ENDPOINTS[$interface]=${PREVIOUS}
        fi

        if ! [ ${ALLOWEDIPS[$interface]+_} ]; then
            ALLOWEDIPS[$interface]=${PARTS[3]}'-'${PARTS[4]}
        else
            PREVIOUS=${ALLOWEDIPS[$interface]}
            PREVIOUS+=','
            PREVIOUS+=${PARTS[3]}
            PREVIOUS+='-'
            PREVIOUS+=${PARTS[4]}
            ALLOWEDIPS[$interface]=${PREVIOUS}
        fi

        if ! [ ${LATESTHANDSHAKE[$interface]+_} ]; then
            LATESTHANDSHAKE[$interface]=${PARTS[3]}'-'${PARTS[5]}
        else
            PREVIOUS=${LATESTHANDSHAKE[$interface]}
            PREVIOUS+=','
            PREVIOUS+=${PARTS[3]}
            PREVIOUS+='-'
            PREVIOUS+=${PARTS[5]}
            LATESTHANDSHAKE[$interface]=${PREVIOUS}
        fi

        if ! [ ${TRANSFERRX[$interface]+_} ]; then
            TRANSFERRX[$interface]=${PARTS[3]}'-'${PARTS[6]}
        else
            PREVIOUS=${TRANSFERRX[$interface]}
            PREVIOUS+=','
            PREVIOUS+=${PARTS[3]}
            PREVIOUS+='-'
            PREVIOUS+=${PARTS[6]}
            TRANSFERRX[$interface]=${PREVIOUS}
        fi
        if ! [ ${TRANSFERTX[$interface]+_} ]; then
            TRANSFERTX[$interface]=${PARTS[3]}'-'${PARTS[7]}
        else
            PREVIOUS=${TRANSFERTX[$interface]}
            PREVIOUS+=','
            PREVIOUS+=${PARTS[3]}
            PREVIOUS+='-'
            PREVIOUS+=${PARTS[7]}
            TRANSFERTX[$interface]=${PREVIOUS}
        fi

        if ! [ ${PERSISTENTKEEPALIVE[$interface]+_} ]; then
            PERSISTENTKEEPALIVE[$interface]=${PARTS[3]}'-'${PARTS[8]}
        else
            PREVIOUS=${PERSISTENTKEEPALIVE[$interface]}
            PREVIOUS+=','
            PREVIOUS+=${PARTS[3]}
            PREVIOUS+='-'
            PREVIOUS+=${PARTS[8]}
            PERSISTENTKEEPALIVE[$interface]=${PREVIOUS}
        fi
    done
done

echo "# HELP wireguard_endpoints The Endpoints of a wireguard interface"
echo "# TYPE wireguard_endpoints Gauge"
for K in "${!ENDPOINTS[@]}"; do
    SAVEIFS=$IFS   # Save current IFS (Internal Field Separator)
    IFS=$','      # Change IFS to newline char
    POINTS=(${ENDPOINTS[$K]}) # split the `names` string into an array by the same name
    IFS=$SAVEIFS   # Restore original IFS

    for POINT in "${POINTS[@]}"; do
        echo "wireguard_endpoints{interface='$K',endpoint='$POINT'} 1"
    done
done

echo "# HELP wireguard_allowedips The AllowedIPs of a wireguard interface"
echo "# TYPE wireguard_allowedips Gauge"
for K in "${!ALLOWEDIPS[@]}"; do
    SAVEIFS=$IFS   # Save current IFS (Internal Field Separator)
    IFS=$','      # Change IFS to newline char
    POINTS=(${ALLOWEDIPS[$K]}) # split the `names` string into an array by the same name
    IFS=$SAVEIFS   # Restore original IFS

    for POINT in "${POINTS[@]}"; do
        SAVEIFS=$IFS   # Save current IFS (Internal Field Separator)
        IFS=$'-'      # Change IFS to newline char
        PARTS=($POINT) # split the `names` string into an array by the same name
        IFS=$SAVEIFS   # Restore original IFS

        echo "wireguard_allowedips{interface='$K',endpoint='${PARTS[0]}',allowedip='${PARTS[1]}'} 1"
    done
done

echo "# HELP wireguard_latesthandshake"
echo "# TYPE wireguard_latesthandshake Gauge"
for K in "${!LATESTHANDSHAKE[@]}"; do
    SAVEIFS=$IFS   # Save current IFS (Internal Field Separator)
    IFS=$','      # Change IFS to newline char
    POINTS=(${LATESTHANDSHAKE[$K]}) # split the `names` string into an array by the same name
    IFS=$SAVEIFS   # Restore original IFS

    for POINT in "${POINTS[@]}"; do
        SAVEIFS=$IFS   # Save current IFS (Internal Field Separator)
        IFS=$'-'      # Change IFS to newline char
        PARTS=($POINT) # split the `names` string into an array by the same name
        IFS=$SAVEIFS   # Restore original IFS

        echo "wireguard_latesthandshake{interface='$K',endpoint='${PARTS[0]}'} ${PARTS[1]}"
    done
done

echo "# HELP wireguard_transferrx"
echo "# TYPE wireguard_transferrx Gauge"
for K in "${!TRANSFERRX[@]}"; do
    SAVEIFS=$IFS   # Save current IFS (Internal Field Separator)
    IFS=$','      # Change IFS to newline char
    POINTS=(${TRANSFERRX[$K]}) # split the `names` string into an array by the same name
    IFS=$SAVEIFS   # Restore original IFS

    for POINT in "${POINTS[@]}"; do
        SAVEIFS=$IFS   # Save current IFS (Internal Field Separator)
        IFS=$'-'      # Change IFS to newline char
        PARTS=($POINT) # split the `names` string into an array by the same name
        IFS=$SAVEIFS   # Restore original IFS

        echo "wireguard_transferrx{interface='$K',endpoint='${PARTS[0]}'} ${PARTS[1]}"
    done
done

echo "# HELP wireguard_transfertx"
echo "# TYPE wireguard_transfertx Gauge"
for K in "${!TRANSFERTX[@]}"; do
    SAVEIFS=$IFS   # Save current IFS (Internal Field Separator)
    IFS=$','      # Change IFS to newline char
    POINTS=(${TRANSFERTX[$K]}) # split the `names` string into an array by the same name
    IFS=$SAVEIFS   # Restore original IFS

    for POINT in "${POINTS[@]}"; do
        SAVEIFS=$IFS   # Save current IFS (Internal Field Separator)
        IFS=$'-'      # Change IFS to newline char
        PARTS=($POINT) # split the `names` string into an array by the same name
        IFS=$SAVEIFS   # Restore original IFS

        echo "wireguard_transfertx{interface='$K',endpoint='${PARTS[0]}'} ${PARTS[1]}"
    done
done

echo "# HELP wireguard_persistentkeepalive"
echo "# TYPE wireguard_persistentkeepalive Gauge"
for K in "${!PERSISTENTKEEPALIVE[@]}"; do
    SAVEIFS=$IFS   # Save current IFS (Internal Field Separator)
    IFS=$','      # Change IFS to newline char
    POINTS=(${PERSISTENTKEEPALIVE[$K]}) # split the `names` string into an array by the same name
    IFS=$SAVEIFS   # Restore original IFS

    for POINT in "${POINTS[@]}"; do
        SAVEIFS=$IFS   # Save current IFS (Internal Field Separator)
        IFS=$'-'      # Change IFS to newline char
        PARTS=($POINT) # split the `names` string into an array by the same name
        IFS=$SAVEIFS   # Restore original IFS

        echo "wireguard_persistentkeepalive{interface='$K',endpoint='${PARTS[0]}'} ${PARTS[1]}"
    done
done