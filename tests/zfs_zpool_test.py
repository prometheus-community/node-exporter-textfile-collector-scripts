from datetime import datetime, timedelta
from zfs_zpool import zpool_status_parse, ZpoolStatus, ZpoolConfig, ZpoolScan
from pathlib import Path


def test_zpool_status_parse_complex():
    assert zpool_status_parse(Path(__file__).parent.joinpath('fixtures/zpool_status_-p').read_text()) == [
        ZpoolStatus(
            name='pool0',
            state='ONLINE',
            configs=[
                ZpoolConfig(name='pool0', path=['pool0'], state='ONLINE', read=0, write=0, checksum=0),
                ZpoolConfig(name='raidz1-0', path=['pool0', 'raidz1-0'], state='ONLINE', read=0, write=0, checksum=0),
                ZpoolConfig(name='ata-TOSHIBA_MG09ACA18TE_82X0A0QMFJDH',
                            path=['pool0', 'raidz1-0', 'ata-TOSHIBA_MG09ACA18TE_82X0A0QMFJDH'], state='ONLINE', read=0,
                            write=0, checksum=0),
                ZpoolConfig(name='ata-TOSHIBA_MG09ACA18TE_82J0A00FFJDH',
                            path=['pool0', 'raidz1-0', 'ata-TOSHIBA_MG09ACA18TE_82J0A00FFJDH'], state='ONLINE', read=0,
                            write=0, checksum=0),
                ZpoolConfig(name='ata-TOSHIBA_MG09ACA18TE_82X0A0QPFJDH',
                            path=['pool0', 'raidz1-0', 'ata-TOSHIBA_MG09ACA18TE_82X0A0QPFJDH'], state='ONLINE', read=0,
                            write=0, checksum=0),
            ],
            scrub=ZpoolScan(at=datetime(2023, 11, 12, 7, 22, 3),
                            duration=timedelta(seconds=25082),
                            corrected=0),
        ),
        ZpoolStatus(
            name='pool1',
            state='ONLINE',
            configs=[
                ZpoolConfig(name='pool1', path=['pool1'], state='ONLINE', read=0, write=0, checksum=0),
                ZpoolConfig(name='mirror-0', path=['pool1', 'mirror-0'], state='ONLINE', read=0, write=0, checksum=0),
                ZpoolConfig(name='nvme-Samsung_SSD_980_500GB_S64DNL0T824602E-part1', path=[
                    'pool1', 'mirror-0', 'nvme-Samsung_SSD_980_500GB_S64DNL0T824602E-part1'], state='ONLINE', read=0,
                            write=0, checksum=0),
                ZpoolConfig(name='nvme-Samsung_SSD_980_500GB_S64DNL0T824555Z-part1',
                            path=['pool1', 'mirror-0', 'nvme-Samsung_SSD_980_500GB_S64DNL0T824555Z-part1'],
                            state='ONLINE', read=0, write=0, checksum=0),
            ],
            scrub=ZpoolScan(at=datetime(2023, 11, 12, 0, 28, 47),
                            duration=timedelta(seconds=285),
                            corrected=1048576),
        ),
    ]


def test_zpool_status_parse_unavail():
    assert zpool_status_parse(Path(__file__).parent.joinpath('fixtures/zpool_status_-p_unavail').read_text()) == [
        ZpoolStatus(
            name='tank',
            state='UNAVAIL',
            configs=[
                ZpoolConfig(name='tank', path=['tank'], state='UNAVAIL', read=0, write=0, checksum=0,
                            comment='insufficient replicas'),
                ZpoolConfig(name='c1t0d0', path=['tank', 'c1t0d0'], state='ONLINE', read=0, write=0, checksum=0),
                ZpoolConfig(name='c1t1d0', path=['tank', 'c1t1d0'], state='UNAVAIL', read=4, write=1, checksum=0,
                            comment='cannot open')
            ]
        )
    ]


def test_zpool_status_parse_degraded_simple():
    assert zpool_status_parse(Path(__file__).parent.joinpath('fixtures/zpool_status_-p_degraded').read_text()) == [
        ZpoolStatus(
            name='tank',
            state='DEGRADED',
            configs=[
                ZpoolConfig(name='tank', path=['tank'], state='DEGRADED', read=0, write=0, checksum=0),
                ZpoolConfig(name='mirror-0', path=['tank', 'mirror-0'], state='DEGRADED', read=0, write=0, checksum=0),
                ZpoolConfig(name='c1t0d0', path=['tank', 'mirror-0', 'c1t0d0'], state='ONLINE', read=0, write=0,
                            checksum=0),
                ZpoolConfig(name='c1t1d0', path=['tank', 'mirror-0', 'c1t1d0'], state='UNAVAIL', read=0, write=0,
                            checksum=0, comment='cannot open'),
            ]
        )
    ]


def test_zpool_status_parse_degraded_with_spare():
    assert zpool_status_parse(
        Path(__file__).parent.joinpath('fixtures/zpool_status_-p_degraded_sparse').read_text()) == [
               ZpoolStatus(name='test', configs=[
                   ZpoolConfig(name='test', path=['test'], state='DEGRADED', read=0, write=0, checksum=0),
                   ZpoolConfig(name='mirror-0', path=['test', 'mirror-0'], state='DEGRADED', read=0, write=0,
                               checksum=0),
                   ZpoolConfig(name='spare-0', path=['test', 'mirror-0', 'spare-0'], state='DEGRADED', read=1, write=0,
                               checksum=0),
                   ZpoolConfig(name='ata-VBOX_HARDDISK_VBb80f1f56-538e9acf',
                               path=['test', 'mirror-0', 'spare-0', 'ata-VBOX_HARDDISK_VBb80f1f56-538e9acf'],
                               state='ONLINE',
                               read=0, write=0, checksum=1),
                   ZpoolConfig(name='pci-0000:00:0d.0-scsi-12:0:0:0-part1',
                               path=['test', 'mirror-0', 'spare-0', 'pci-0000:00:0d.0-scsi-12:0:0:0-part1'],
                               state='FAULTED',
                               read=0, write=0, checksum=0,
                               comment='was /dev/disk/by-path/pci-0000:00:0d.0-scsi-12:0:0:0-part1'),
                   ZpoolConfig(name='ata-VBOX_HARDDISK_VB875e28a5-4b293298',
                               path=['test', 'mirror-0', 'ata-VBOX_HARDDISK_VB875e28a5-4b293298'], state='ONLINE',
                               read=0,
                               write=0, checksum=0),
                   ZpoolConfig(name='mirror-1', path=['test', 'mirror-1'], state='ONLINE', read=0, write=0, checksum=0),
                   ZpoolConfig(name='ata-VBOX_HARDDISK_VB4145ff65-9b1320a3',
                               path=['test', 'mirror-1', 'ata-VBOX_HARDDISK_VB4145ff65-9b1320a3'], state='ONLINE',
                               read=0,
                               write=0, checksum=0),
                   ZpoolConfig(name='ata-VBOX_HARDDISK_VBee9d66a1-edf52bff',
                               path=['test', 'mirror-1', 'ata-VBOX_HARDDISK_VBee9d66a1-edf52bff'], state='ONLINE',
                               read=0,
                               write=0, checksum=0),
                   ZpoolConfig(name='pci-0000:00:0d.0-scsi-10:0:0:0', path=['spares', 'pci-0000:00:0d.0-scsi-10:0:0:0'],
                               state='AVAIL', is_spare=True),
                   ZpoolConfig(name='pci-0000:00:0d.0-scsi-11:0:0:0', path=['spares', 'pci-0000:00:0d.0-scsi-11:0:0:0'],
                               state='AVAIL', is_spare=True),
                   ZpoolConfig(name='pci-0000:00:0d.0-scsi-12:0:0:0', path=['spares', 'pci-0000:00:0d.0-scsi-12:0:0:0'],
                               state='AVAIL', is_spare=True),
                   ZpoolConfig(name='pci-0000:00:0d.0-scsi-13:0:0:0', path=['spares', 'pci-0000:00:0d.0-scsi-13:0:0:0'],
                               state='AVAIL', is_spare=True),
               ], state='DEGRADED',
                           resilvering=ZpoolScan(at=datetime(2014, 8, 22, 12, 2, 46),
                                                 duration=timedelta(0),
                                                 corrected=27053261)
                           )
           ]


def test_zpool_status_parse_resilvered():
    assert zpool_status_parse(
        Path(__file__).parent.joinpath('fixtures/zpool_status_-p_resilvered').read_text()) == [
               ZpoolStatus(name='rpool',
                           state='DEGRADED',
                           configs=[ZpoolConfig(name='rpool', path=['rpool'], state='DEGRADED', read=0, write=0,
                                                checksum=0, ),
                                    ZpoolConfig(name='mirror-0', path=['rpool', 'mirror-0'], state='DEGRADED', read=0,
                                                write=0, checksum=0, ),
                                    ZpoolConfig(name='c4d1s0', path=['rpool', 'mirror-0', 'c4d1s0'], state='UNAVAIL',
                                                read=0, write=0, checksum=0, comment='cannot open'),
                                    ZpoolConfig(name='c2t1d0s0', path=['rpool', 'mirror-0', 'c2t1d0s0'], state='ONLINE',
                                                read=0, write=0, checksum=0),
                                    ZpoolConfig(name='c3d1s0', path=['rpool', 'mirror-0', 'c3d1s0'], state='UNAVAIL',
                                                read=0, write=0, checksum=0, comment='cannot open')],
                           resilvering=ZpoolScan(at=datetime(2011, 11, 15, 5, 31, 36),
                                                 duration=timedelta(seconds=0),
                                                 corrected=1478492),
                           ),
               ZpoolStatus(name='zpool',
                           state='UNAVAIL',
                           configs=[
                               ZpoolConfig(name='zpool', path=['zpool'], state='UNAVAIL', read=0, write=0, checksum=0,
                                           comment='insufficient replicas'),
                               ZpoolConfig(name='raidz1-0', path=['zpool', 'raidz1-0'], state='UNAVAIL', read=0,
                                           write=0, checksum=0, comment='insufficient replicas'),
                               ZpoolConfig(name='c2t1d0p2', path=['zpool', 'raidz1-0', 'c2t1d0p2'], state='ONLINE',
                                           read=0, write=0, checksum=0),
                               ZpoolConfig(name='c4d1p2', path=['zpool', 'raidz1-0', 'c4d1p2'], state='UNAVAIL', read=0,
                                           write=0, checksum=0, comment='cannot open'),
                               ZpoolConfig(name='c3d1p2', path=['zpool', 'raidz1-0', 'c3d1p2'], state='UNAVAIL', read=0,
                                           write=0, checksum=0, comment='cannot open')],
                           )
           ]


def test_zpool_status_scrub():
    assert zpool_status_parse(
        Path(__file__).parent.joinpath('fixtures/zpool_status_-p_scrub').read_text()) == [
               ZpoolStatus(name='freenas-boot',
                           state='ONLINE',
                           configs=[
                               ZpoolConfig(name='freenas-boot', path=['freenas-boot'], state='ONLINE', read=0, write=0,
                                           checksum=0),
                               ZpoolConfig(name='da0p2', path=['freenas-boot', 'da0p2'], state='ONLINE', read=0,
                                           write=0, checksum=0)],
                           scrub=ZpoolScan(at=datetime(2017, 1, 25, 3, 47, 27),
                                           duration=timedelta(seconds=120),
                                           corrected=0)
                           ),
               ZpoolStatus(name='nas_zfs_vol0',
                           state='ONLINE',
                           configs=[
                               ZpoolConfig(name='nas_zfs_vol0', path=['nas_zfs_vol0'], state='ONLINE', read=0, write=0,
                                           checksum=0),
                               ZpoolConfig(name='mirror-0', path=['nas_zfs_vol0', 'mirror-0'], state='ONLINE', read=0,
                                           write=0,
                                           checksum=0),
                               ZpoolConfig(name='gptid/a855d0c8-5218-11e3-9e38-10604b926998',
                                           path=['nas_zfs_vol0', 'mirror-0',
                                                 'gptid/a855d0c8-5218-11e3-9e38-10604b926998'],
                                           state='ONLINE', read=0, write=0, checksum=0),
                               ZpoolConfig(name='gptid/a8c3fe2f-5218-11e3-9e38-10604b926998',
                                           path=['nas_zfs_vol0', 'mirror-0',
                                                 'gptid/a8c3fe2f-5218-11e3-9e38-10604b926998'],
                                           state='ONLINE', read=0, write=0, checksum=0),
                               ZpoolConfig(name='mirror-1', path=['nas_zfs_vol0', 'mirror-1'], state='ONLINE', read=0,
                                           write=0,
                                           checksum=0),
                               ZpoolConfig(name='gptid/a91ebd06-5218-11e3-9e38-10604b926998',
                                           path=['nas_zfs_vol0', 'mirror-1',
                                                 'gptid/a91ebd06-5218-11e3-9e38-10604b926998'],
                                           state='ONLINE', read=0, write=0, checksum=0),
                               ZpoolConfig(name='gptid/a96f4d37-5218-11e3-9e38-10604b926998',
                                           path=['nas_zfs_vol0', 'mirror-1',
                                                 'gptid/a96f4d37-5218-11e3-9e38-10604b926998'],
                                           state='ONLINE', read=0, write=0, checksum=0),
                           ],
                           scrub=ZpoolScan(at=datetime(2017, 1, 8, 7, 7, 22),
                                           duration=timedelta(seconds=25620),
                                           corrected=0)
                           )
           ]


def test_zpool_status_logs():
    assert zpool_status_parse(
        Path(__file__).parent.joinpath('fixtures/zpool_status_-p_logs').read_text()) == [
               ZpoolStatus(name='zones',
                           state='DEGRADED',
                           configs=[
                               ZpoolConfig(name='zones', path=['zones'], state='DEGRADED', read=0, write=0, checksum=0),
                               ZpoolConfig(name='mirror-0', path=['zones', 'mirror-0'], state='DEGRADED', read=0,
                                           write=0, checksum=0),
                               ZpoolConfig(name='c0t5000C5006349E003d0s0',
                                           path=['zones', 'mirror-0', 'c0t5000C5006349E003d0s0'], state='UNAVAIL',
                                           read=0, write=0, checksum=0, comment='was /dev/dsk/c0t5000C5006349E003d0s0'),
                               ZpoolConfig(name='c0t5000C500631F81E7d0',
                                           path=['zones', 'mirror-0', 'c0t5000C500631F81E7d0'], state='ONLINE', read=0,
                                           write=0, checksum=0),
                               ZpoolConfig(name='mirror-1', path=['zones', 'mirror-1'], state='ONLINE', read=0, write=0,
                                           checksum=0),
                               ZpoolConfig(name='c0t5000C500634A297Bd0',
                                           path=['zones', 'mirror-1', 'c0t5000C500634A297Bd0'], state='ONLINE', read=0,
                                           write=0, checksum=0),
                               ZpoolConfig(name='c0t5000C500634B4EA3d0',
                                           path=['zones', 'mirror-1', 'c0t5000C500634B4EA3d0'], state='ONLINE', read=0,
                                           write=0, checksum=0), ZpoolConfig(name='logs', path=['logs'], state=''),
                               ZpoolConfig(name='c0t55CD2E404B73663Dd0', path=['logs', 'c0t55CD2E404B73663Dd0'],
                                           state='ONLINE', read=0, write=0, checksum=0)
                           ],
                           scrub=ZpoolScan(at=datetime(2016, 7, 14, 18, 42, 6),
                                           duration=timedelta(seconds=106620),
                                           corrected=0),
                           )
           ]


def test_zpool_status_parse_empty():
    assert zpool_status_parse('') == []
    assert zpool_status_parse('\n\n') == []


def test_zpool_status_parse_garbage():
    assert zpool_status_parse('pool: foo\npool: bar') == []
