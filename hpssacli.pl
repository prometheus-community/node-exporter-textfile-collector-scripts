#!/usr/bin/perl
#
# Script to parse HPACUCLI/HPSSACLI's JSON output and expose
# HP SmartArray health as Prometheus metrics.
#
# Tested against HPE Smart Storage Administrator (hpssacli) '2.40.13.0'.
#
# Based on storcli node_exporter example
#
# (c) 2019, Nuno Tavares <n.tavares@portavita.eu>
#
# You can find the latest version in:
# https://github.com/ntavares/node-exporter-textfile-collector-scripts
#

use strict;
use warnings;

# These may need changing depending on the configuration of your system
my $hpacucli = '/usr/sbin/hpssacli';
my $sudo     = '/usr/bin/sudo';
my $hpacucli_cmd = "$hpacucli";

my ( $slot, $fh, $fh2 );

sub exp_exit {
   my ($text) = @_;
   print STDERR $text;
   exit(1);
}

sub add_metric {
    my $name = shift;
    my $labelsref = shift;
    my $value = shift;

    my @la = ();
    foreach my $k (keys %{$labelsref}) {
        my $t = "$k=\"" . $labelsref->{$k} . "\"";
        push @la, $t;
    }

    print "hpsa_" . $name . "{" . join(",", @la) . "}" . " " . $value . "\n";
}


# Check hpacucli is installed
if ( !-e $hpacucli ) {
    exp_exit("Can't find HP CLI binary: " . $hpacucli . "\n");
}

# Get controller status
open( $fh, "$hpacucli_cmd controller all show status|" )
  or exp_exit( "Failed to run $hpacucli_cmd" );


# Spin through output
foreach my $line (<$fh>) {

    if ( $line =~ m/Another instance of hpacucli is running! Stop it first\./i )
    {
        exp_exit( "Another instance of hpacucli is running!" );
    }

    elsif ( $line =~ m/Slot (\d+)/i ) {
        $slot = $1;

        # Now get further status on each controller elements
        foreach my $PARAM (qw(array physicaldrive logicaldrive)) {

            open( $fh2,
                "$hpacucli_cmd controller slot=$slot $PARAM all show status|"
              )
              or exp_exit( "Failed to get info for $PARAM slot $slot" );

            foreach my $line2 (<$fh2>) {
                if ( $line2 =~ /^\s*$PARAM ([^\s]+).*:\s*(\w+[\w\s]*)$/i ) {
                    my $pbb = $1;
                    my $result = $2;
                    chomp $result;
                    my %l = ( "slot" => $slot, "locid" => $pbb );
                    &add_metric($PARAM . "_status", \%l, (( $result ne "OK" )?"0":"1"));
                }
            }

            close($fh2)
              or exp_exit( "Failed to get info for $PARAM slot $slot" );
        }

        # Now get further details on each physicaldrive
        open( $fh2,
            "$hpacucli_cmd controller slot=$slot physicaldrive all show detail|"
          )
          or exp_exit( "Failed to get info for physicaldrive slot $slot" );

        my %pdlist = ();
        my $cur_pd = '';

        foreach my $line2 (<$fh2>) {
            if ( $line2 =~ /^\s+physicaldrive ([^\s]+)$/i ) {
                $cur_pd = $1;
                $pdlist{$cur_pd} = ();
            } elsif ( $line2 =~ /^\s+Rotational Speed: (\d+)$/i ) {
                $pdlist{$cur_pd}{"speed"} = $1;
            } elsif ( $line2 =~ /^\s+Firmware Revision: (.+)$/i ) {
                $pdlist{$cur_pd}{"revision"} = $1;
            } elsif ( $line2 =~ /^\s+Serial Number: (.+)$/i ) {
                $pdlist{$cur_pd}{"serial"} = $1;
            } elsif ( $line2 =~ /^\s+Model: (.+)$/i ) {
                $pdlist{$cur_pd}{"model"} = $1;
            } elsif ( $line2 =~ /^\s+Current Temperature \(C\): (.+)$/i ) {
                my $temp = $1;
                my %l = ( "slot" => $slot, "locid" => $cur_pd );
                &add_metric('physicaldrive_current_temperature', \%l, $temp);
            } elsif ( $line2 =~ /^\s+PHY Transfer Rate: (.+)$/i ) {
                my $phyrate = $1;
                $phyrate =~ s/^([0-9\.]+).*$/$1/g;
                my %l = ( "slot" => $slot, "locid" => $cur_pd );
                &add_metric('physicaldrive_phy_transfer_rate', \%l, $phyrate);
            }
        }
        foreach my $pd (keys %pdlist) {
            &add_metric('physicaldrive_info', $pdlist{$pd}, 1);
        }

        close($fh2)
          or exp_exit( "Failed to get info for physicaldrive slot $slot" );


    }
    else {
        # Check the overall controller status is OK
        if ( $line =~ /^\s+(.*? Status):\s*([\w\s]+).*$/ ) {
            my $name = lc $1;
            my $result = $2;
            $name =~ s/[^a-zA-z0-9]/_/g;
            chomp($result);
            my %l = ( "slot" => $slot );
            &add_metric($name, \%l, (( $result ne "OK" )?"0":"1"));
        }

    }
}
close($fh)
  or exp_exist("Failed to run $hpacucli_cmd controller all show status" );


